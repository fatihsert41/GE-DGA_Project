using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class PinVeOturum : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "FailedAttempts",
                table: "technicians",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<DateTime>(
                name: "LockedUntil",
                table: "technicians",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "PinHash",
                table: "technicians",
                type: "TEXT",
                maxLength: 100,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "PinSalt",
                table: "technicians",
                type: "TEXT",
                maxLength: 50,
                nullable: false,
                defaultValue: "");

            migrationBuilder.CreateTable(
                name: "sessions",
                columns: table => new
                {
                    TokenHash = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    TechnicianId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    ExpiresAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_sessions", x => x.TokenHash);
                    table.ForeignKey(
                        name: "FK_sessions_technicians_TechnicianId",
                        column: x => x.TechnicianId,
                        principalTable: "technicians",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-01",
                columns: new[] { "FailedAttempts", "LockedUntil", "PinHash", "PinSalt" },
                values: new object[] { 0, null, "", "" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-02",
                columns: new[] { "FailedAttempts", "LockedUntil", "PinHash", "PinSalt" },
                values: new object[] { 0, null, "", "" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-03",
                columns: new[] { "FailedAttempts", "LockedUntil", "PinHash", "PinSalt" },
                values: new object[] { 0, null, "", "" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-04",
                columns: new[] { "FailedAttempts", "LockedUntil", "PinHash", "PinSalt" },
                values: new object[] { 0, null, "", "" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-05",
                columns: new[] { "FailedAttempts", "LockedUntil", "PinHash", "PinSalt" },
                values: new object[] { 0, null, "", "" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-06",
                columns: new[] { "FailedAttempts", "LockedUntil", "PinHash", "PinSalt" },
                values: new object[] { 0, null, "", "" });

            migrationBuilder.CreateIndex(
                name: "IX_sessions_ExpiresAt",
                table: "sessions",
                column: "ExpiresAt");

            migrationBuilder.CreateIndex(
                name: "IX_sessions_TechnicianId",
                table: "sessions",
                column: "TechnicianId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "sessions");

            migrationBuilder.DropColumn(
                name: "FailedAttempts",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "LockedUntil",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "PinHash",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "PinSalt",
                table: "technicians");
        }
    }
}
