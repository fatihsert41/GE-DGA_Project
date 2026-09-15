using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace TransformerAI.Maintenance.Tests.Integration;

/// <summary>Testler için ince HTTP yardımcısı: istek at, kodu ve JSON'u al.</summary>
/// <remarks>
/// Testin okunur kalması için: her test "şu isteği at, şu kodu bekle" diye
/// yazılabilsin, başlık ve JSON ayrıştırma gürültüsü burada kalsın.
/// </remarks>
public sealed class ApiClient
{
    private readonly HttpClient _http;

    public ApiClient(HttpClient http)
    {
        _http = http;
    }

    public sealed record Response(HttpStatusCode Status, JsonElement Body)
    {
        public int Code => (int)Status;

        public string Str(string name) => Body.GetProperty(name).GetString() ?? "";

        public JsonElement Get(string name) => Body.GetProperty(name);

        public IReadOnlyList<string> Strings(string name) =>
            Body.GetProperty(name).EnumerateArray().Select(e => e.GetString() ?? "").ToList();

        /// <summary>Hata gövdesindeki mesaj (yoksa boş).</summary>
        public string Message =>
            Body.ValueKind == JsonValueKind.Object && Body.TryGetProperty("message", out var m)
                ? m.GetString() ?? ""
                : "";
    }

    public async Task<Response> SendAsync(HttpMethod method, string path,
                                          object? body = null, string? token = null)
    {
        using var request = new HttpRequestMessage(method, path);
        if (body is not null)
            request.Content = JsonContent.Create(body);
        if (token is not null)
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);

        using var response = await _http.SendAsync(request);
        var text = await response.Content.ReadAsStringAsync();

        JsonElement json = default;
        if (!string.IsNullOrWhiteSpace(text))
        {
            try { json = JsonDocument.Parse(text).RootElement.Clone(); }
            catch (JsonException) { /* JSON olmayan cevap: gövde boş sayılır */ }
        }
        return new Response(response.StatusCode, json);
    }

    public Task<Response> Get(string path, string? token = null) =>
        SendAsync(HttpMethod.Get, path, null, token);

    public Task<Response> Post(string path, object? body = null, string? token = null) =>
        SendAsync(HttpMethod.Post, path, body, token);

    public Task<Response> Put(string path, object? body, string? token = null) =>
        SendAsync(HttpMethod.Put, path, body, token);

    public Task<Response> Patch(string path, object? body, string? token = null) =>
        SendAsync(HttpMethod.Patch, path, body, token);

    public Task<Response> Login(string employeeNo, string password) =>
        Post("/auth/login", new { employeeNo, password });

    /// <summary>Demo geçici parolasıyla girer, parolayı değiştirir; yetkili cevabı döner.</summary>
    public async Task<Response> ActivateAsync(string employeeNo, string newPassword)
    {
        var temporary = $"Demo-{employeeNo}";
        var login = await Login(employeeNo, temporary);
        Assert.True(login.Status == HttpStatusCode.OK,
                    $"{employeeNo} geçici giriş: {login.Code} {login.Message}");

        var changed = await Post("/auth/change-password",
            new { currentPassword = temporary, newPassword }, login.Str("token"));
        Assert.True(changed.Status == HttpStatusCode.OK,
                    $"{employeeNo} parola değiştirme: {changed.Code} {changed.Message}");
        return changed;
    }

    /// <summary>Etkinleştirir ve yalnızca belirteci döner.</summary>
    public async Task<string> TokenFor(string employeeNo, string newPassword) =>
        (await ActivateAsync(employeeNo, newPassword)).Str("token");
}
