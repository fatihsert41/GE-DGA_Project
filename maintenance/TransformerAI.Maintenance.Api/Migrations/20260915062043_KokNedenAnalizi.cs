using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class KokNedenAnalizi : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "root_cause_analyses",
                columns: table => new
                {
                    Id = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    WorkOrderId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    TransformerId = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    FailureMode = table.Column<string>(type: "TEXT", maxLength: 30, nullable: false),
                    Finding = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    RootCause = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    CorrectiveAction = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    PreventiveAction = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    RecordedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    RecordedById = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    RecordedByName = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    RecordedByEmployeeNo = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_root_cause_analyses", x => x.Id);
                    table.ForeignKey(
                        name: "FK_root_cause_analyses_work_orders_WorkOrderId",
                        column: x => x.WorkOrderId,
                        principalTable: "work_orders",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_root_cause_analyses_FailureMode",
                table: "root_cause_analyses",
                column: "FailureMode");

            migrationBuilder.CreateIndex(
                name: "IX_root_cause_analyses_TransformerId",
                table: "root_cause_analyses",
                column: "TransformerId");

            migrationBuilder.CreateIndex(
                name: "IX_root_cause_analyses_WorkOrderId",
                table: "root_cause_analyses",
                column: "WorkOrderId",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "root_cause_analyses");
        }
    }
}
