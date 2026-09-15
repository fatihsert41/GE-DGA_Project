using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class SistemYonetimi : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "technicians",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "CreatedByName",
                table: "technicians",
                type: "TEXT",
                maxLength: 130,
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "DeactivatedAt",
                table: "technicians",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "DeactivationReason",
                table: "technicians",
                type: "TEXT",
                maxLength: 500,
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "LastLoginAt",
                table: "technicians",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "MustChangePassword",
                table: "technicians",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "PasswordChangedAt",
                table: "technicians",
                type: "TEXT",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "user_audit_events",
                columns: table => new
                {
                    Id = table.Column<long>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    At = table.Column<DateTime>(type: "TEXT", nullable: false),
                    Action = table.Column<string>(type: "TEXT", maxLength: 40, nullable: false),
                    TargetId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    TargetEmployeeNo = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    TargetName = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    ActorId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: true),
                    ActorEmployeeNo = table.Column<string>(type: "TEXT", maxLength: 20, nullable: true),
                    ActorName = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    Detail = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_user_audit_events", x => x.Id);
                });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-01",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-02",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-03",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-04",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-05",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-06",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-07",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-08",
                columns: new[] { "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "LastLoginAt", "MustChangePassword", "PasswordChangedAt" },
                values: new object[] { null, null, null, null, null, false, null });

            migrationBuilder.InsertData(
                table: "technicians",
                columns: new[] { "Id", "CreatedAt", "CreatedByName", "DeactivatedAt", "DeactivationReason", "Department", "EmployeeNo", "FailedAttempts", "IsActive", "LastLoginAt", "LockedUntil", "MaxOpenOrders", "MustChangePassword", "Name", "PasswordChangedAt", "PinHash", "PinSalt", "Role", "Specialty" },
                values: new object[] { "TK-09", null, null, null, null, "SystemAdmin", "10001", 0, true, null, null, 0, false, "Kerem Aksoy", null, "", "", "Engineer", "General" });

            migrationBuilder.CreateIndex(
                name: "IX_user_audit_events_At",
                table: "user_audit_events",
                column: "At");

            migrationBuilder.CreateIndex(
                name: "IX_user_audit_events_TargetId",
                table: "user_audit_events",
                column: "TargetId");

            // ⚠ ELLE EKLENDİ — EF bunu üretmez, çünkü şema değil VERİ kararı.
            //
            // Faz 9.0b'deki 4 haneli PIN özetleri silinir. Silinmeseydi
            // kullanıcılar eski PIN'le (ör. "0502") girmeye devam eder ve
            // parola değiştirmeye hiç zorlanmazdı: uygulamanın açılış bloğu
            // yalnızca parolası BOŞ olan hesaplara geçici parola atıyor.
            //
            // Açık oturumlar da silinir: eski belirteçler PIN döneminde,
            // yeni departman haritasından önce üretildi.
            //
            // Geri alınamaz (Down PIN'leri geri getirmez) — bilinçli: bir
            // parolayı zayıf bir PIN'e "geri döndürmek" isteyeceğimiz bir
            // senaryo yok.
            migrationBuilder.Sql(
                "UPDATE technicians SET PinHash = '', PinSalt = '', " +
                "FailedAttempts = 0, LockedUntil = NULL;");
            migrationBuilder.Sql("DELETE FROM sessions;");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "user_audit_events");

            migrationBuilder.DeleteData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-09");

            migrationBuilder.DropColumn(
                name: "CreatedAt",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "CreatedByName",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "DeactivatedAt",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "DeactivationReason",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "LastLoginAt",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "MustChangePassword",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "PasswordChangedAt",
                table: "technicians");
        }
    }
}
