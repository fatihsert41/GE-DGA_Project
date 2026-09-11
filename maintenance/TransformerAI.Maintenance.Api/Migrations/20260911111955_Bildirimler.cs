using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class Bildirimler : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "notifications",
                columns: table => new
                {
                    Id = table.Column<string>(type: "TEXT", maxLength: 40, nullable: false),
                    WorkOrderId = table.Column<string>(type: "TEXT", maxLength: 40, nullable: false),
                    RecipientId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    RecipientName = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    RecipientEmployeeNo = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Channel = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Status = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Subject = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Body = table.Column<string>(type: "TEXT", nullable: false),
                    Trigger = table.Column<string>(type: "TEXT", maxLength: 40, nullable: false),
                    Priority = table.Column<double>(type: "REAL", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    SentAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    ReadAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    Attempts = table.Column<int>(type: "INTEGER", nullable: false),
                    LastError = table.Column<string>(type: "TEXT", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_notifications", x => x.Id);
                    table.ForeignKey(
                        name: "FK_notifications_technicians_RecipientId",
                        column: x => x.RecipientId,
                        principalTable: "technicians",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_notifications_work_orders_WorkOrderId",
                        column: x => x.WorkOrderId,
                        principalTable: "work_orders",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_notifications_RecipientId_Status",
                table: "notifications",
                columns: new[] { "RecipientId", "Status" });

            migrationBuilder.CreateIndex(
                name: "IX_notifications_Status",
                table: "notifications",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_notifications_WorkOrderId_RecipientId_Trigger",
                table: "notifications",
                columns: new[] { "WorkOrderId", "RecipientId", "Trigger" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "notifications");
        }
    }
}
