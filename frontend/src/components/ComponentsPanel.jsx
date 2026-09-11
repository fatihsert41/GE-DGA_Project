import { useCallback, useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import api from '../api'
import { axis, grid, tooltip, muted, SERIES } from '../theme'

/* Faz 9.4 — Buşing ve kademe değiştirici.
 *
 * Şimdiye kadarki her ölçüt trafonun AKTİF KISMINI (sargı, yağ, kağıt)
 * değerlendiriyordu. Ama arızaların önemli bir kısmı eklentilerden gelir.
 *
 * Bu ekranda iki farklı ölçüt mantığı yan yana duruyor ve farkları
 * öğreticidir:
 *
 *   BUŞİNG → ölçüt DEĞİŞİM. Kapasitans künyede yazar; sapma, bir
 *            kondansatör katmanının delindiğini gösterir.
 *   OLTC   → ölçüt KULLANIM. Kontak aşınması takvimle değil işletme
 *            sayısıyla ilerler.
 */

const COND_CLASS = {
  'iyi': 'low', 'kabul': 'medium', 'kötü': 'critical', 'bilinmiyor': '',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

const Badge = ({ condition }) => (
  <span className={`badge sm ${COND_CLASS[condition] || ''}`}>
    {condition || 'bilinmiyor'}
  </span>
)

function Bushings({ section, series, schema }) {
  if (!section?.available) {
    return (
      <div className="panel">
        <h2>Buşingler</h2>
        <p className="empty">{section?.reason || 'Ölçüm yok.'}</p>
      </div>
    )
  }

  const chart = (series || []).map((s) => ({
    date: fmtDate(s.tested_at), A: s.A, B: s.B, C: s.C,
  }))

  return (
    <div className="panel">
      <div className="el-head">
        <div>
          <h2>Buşingler <Badge condition={section.overall} /></h2>
          <p className="note el-meaning">{section.meaning}</p>
        </div>
        <span className="el-standard">{section.standard}</span>
      </div>

      <div className="table-scroll">
        <table className="compare">
          <thead>
            <tr>
              <th>Faz</th><th>Güç faktörü</th><th>Ölçülen C1</th>
              <th>Künye C1</th><th>Sapma</th><th>Durum</th>
            </tr>
          </thead>
          <tbody>
            {section.phases.map((p) => (
              <tr key={p.phase}>
                <td><b>{p.phase}</b></td>
                <td className="num">
                  {p.pf_pct == null ? '—' : `%${p.pf_pct}`}
                </td>
                <td className="num">{p.capacitance_pf ?? '—'}</td>
                <td className="num muted">{p.rated_pf ?? '—'}</td>
                <td className={p.cap_condition === 'kötü'
                  ? 'over-limit num' : 'num'}>
                  {p.deviation_pct == null ? '—'
                    : `${p.deviation_pct >= 0 ? '+' : '−'}%${Math.abs(p.deviation_pct)}`}
                </td>
                <td><Badge condition={p.condition} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {section.problems.length > 0 && (
        <div className={`el-note ${section.data_suspect ? 'stop' : 'warn'}`}>
          <b>{section.data_suspect ? 'Veri şüpheli.' : 'Bulgu.'}</b>
          <ul style={{ margin: '6px 0 0' }}>
            {section.problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        </div>
      )}

      <p className="note">
        Ölçüt <b>mutlak kapasitans değil, künyeden SAPMA</b>. Mutlak değer
        buşing tasarımına göre değişir ve tek başına bir şey söylemez —
        tıpkı sargı direncinde olduğu gibi. Sapma ise doğrudan fiziksel
        bir anlam taşır: %5 sapma, kondansatör katmanlarının yaklaşık
        %5'inin kısa devre olması demektir. Süreç hızlanarak ilerler,
        çünkü kalan katmanların üzerindeki gerilim artar.
        {schema && (
          <> Sınırlar: sapma %{schema.cap_good} iyi, %{schema.cap_accept}
            {' '}kabul · güç faktörü %{schema.pf_good} iyi.</>
        )}
      </p>

      {chart.length > 1 && (
        <>
          <h3>Kapasitans Sapmasının Seyri</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chart}
              margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
              <CartesianGrid stroke={grid.stroke} vertical={false} />
              <XAxis dataKey="date" stroke={axis.stroke} tick={axis.tick} />
              <YAxis stroke={axis.stroke} tick={axis.tick} unit="%" width={55} />
              <Tooltip {...tooltip} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={2} stroke={muted} strokeDasharray="4 4" />
              <ReferenceLine y={-2} stroke={muted} strokeDasharray="4 4" />
              {['A', 'B', 'C'].map((ph, i) => (
                <Line key={ph} type="monotone" dataKey={ph} name={`${ph} fazı`}
                  stroke={SERIES[i]} strokeWidth={2} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <p className="note">
            Tek ölçüm sınırın altında olsa bile <b>eğilim</b> uyarı verir:
            %1.5 sapma tek başına kabul edilebilir, ama iki yılda %0.3'ten
            %1.5'e çıkmışsa katmanlar delinmeye devam ediyor demektir.
          </p>
        </>
      )}
    </div>
  )
}

function Oltc({ section, total, schema }) {
  if (!section?.available) {
    return (
      <div className="panel">
        <h2>Kademe Değiştirici</h2>
        <p className="empty">{section?.reason || 'Veri yok.'}</p>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="el-head">
        <div>
          <h2>Kademe Değiştirici <Badge condition={section.overall} /></h2>
          <p className="note el-meaning">{section.meaning}</p>
        </div>
        <span className="el-standard">{section.standard}</span>
      </div>

      <div className="el-metric">
        {section.checks.map((c) => (
          <div key={c.key}>
            <div className="k">{c.label}</div>
            <b className={`el-big ${COND_CLASS[c.condition]}`}>{c.value}</b>
            <div className="muted">
              {c.unit} · sınır {c.limit}
            </div>
          </div>
        ))}
      </div>

      <div className="tmeta" style={{ marginTop: 18 }}>
        {total != null && (
          <>
            <span className="k">Toplam işletme</span>
            <span className="num">{total.toLocaleString('tr-TR')}</span>
          </>
        )}
      </div>

      <div className="table-scroll" style={{ marginTop: 12 }}>
        <table className="compare">
          <thead>
            <tr><th>Ölçüt</th><th>Değer</th><th>Sınır</th>
              <th>Durum</th><th>Neden</th></tr>
          </thead>
          <tbody>
            {section.checks.map((c) => (
              <tr key={c.key}>
                <td><b>{c.label}</b></td>
                <td className="num">{c.value} {c.unit}</td>
                <td className="num muted">{c.limit}</td>
                <td><Badge condition={c.condition} /></td>
                <td className="muted insp-why">{c.meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="note">
        Ölçüt <b>kullanımdır, durum değil</b>: kontak aşınması takvimle
        değil işletme sayısıyla ilerler. 80.000 kez çalışmış bir
        mekanizma, bugün iyi görünse bile revizyon ister. Buna karşılık
        az çalışan bir OLTC'de sayaç dolmasa da <b>süre dolar</b> — yağ
        yaşlanır, contalar sertleşir.
        {schema && (
          <> Sınırlar: {schema.operations_limit.toLocaleString('tr-TR')}
            {' '}işletme ya da {schema.years_limit} yıl, hangisi önce
            dolarsa.</>
        )}
      </p>
    </div>
  )
}

export default function ComponentsPanel({ id }) {
  const [data, setData] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    api.componentTests(id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { setData(null); load() }, [id, load])
  useEffect(() => {
    api.componentsSchema().then(setSchema).catch(() => setSchema(null))
  }, [])

  if (error) return <div className="panel"><p className="empty">Hata: {error}</p></div>
  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  if (!data.available) {
    return (
      <div className="panel">
        <h2>Buşing ve Kademe Değiştirici</h2>
        <p className="empty">{data.message}</p>
        <p className="note">
          Bu testler elektriksel testlerle birlikte, planlı kesintide
          yapılır. Aktif kısmı (sargı, yağ, kağıt) ölçen hiçbir yöntem
          buşing ya da kademe durumunu göstermez — bu yüzden ayrı bir
          boyut.
        </p>
      </div>
    )
  }

  const a = data.latest_assessment
  const latest = data.tests[data.tests.length - 1]

  return (
    <div>
      <div className="panel">
        <h2>Buşing ve Kademe Değiştirici <Badge condition={a.overall} /></h2>
        <div className="tmeta">
          <span className="k">Son test</span>
          <span>{fmtDate(latest.tested_at)}
            {latest.recorded_by_name && (
              <span className="muted"> · {latest.recorded_by_name}</span>)}
          </span>
          <span className="k">Geçmiş</span><span>{data.n_tests} test</span>
        </div>

        {a.problems.length > 0 && (
          <div className="np-problems">
            <b>Bulgular</b>
            <ul>{a.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}

        <p className="note">
          Bu bölüm trafonun <b>eklentilerini</b> değerlendirir. Aktif
          kısım (sargı, yağ, kağıt) sağlıklı olsa bile buşing ya da kademe
          değiştirici arızalanabilir — ve buşing arızası şiddetli biter.
        </p>
      </div>

      <Bushings section={a.sections.bushings} series={data.deviation_series}
        schema={schema?.bushings} />
      <Oltc section={a.sections.oltc}
        total={a.sections.oltc?.total_operations} schema={schema?.oltc} />
    </div>
  )
}
