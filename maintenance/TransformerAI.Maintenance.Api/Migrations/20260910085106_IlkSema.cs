using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class IlkSema : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "work_orders",
                columns: table => new
                {
                    Id = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    TransformerId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Kind = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Reason = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Priority = table.Column<double>(type: "REAL", nullable: false),
                    AssignedTo = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    DueDate = table.Column<DateOnly>(type: "TEXT", nullable: true),
                    CompletedAt = table.Column<DateTime>(type: "TEXT", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_work_orders", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_work_orders_Status",
                table: "work_orders",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_work_orders_TransformerId",
                table: "work_orders",
                column: "TransformerId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "work_orders");
        }
    }
}
