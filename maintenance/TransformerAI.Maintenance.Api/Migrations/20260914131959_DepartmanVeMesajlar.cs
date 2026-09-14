using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class DepartmanVeMesajlar : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "Department",
                table: "technicians",
                type: "TEXT",
                maxLength: 30,
                nullable: false,
                defaultValue: "FieldService");

            migrationBuilder.AlterColumn<string>(
                name: "WorkOrderId",
                table: "notifications",
                type: "TEXT",
                maxLength: 40,
                nullable: true,
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldMaxLength: 40);

            migrationBuilder.AddColumn<string>(
                name: "MessageId",
                table: "notifications",
                type: "TEXT",
                maxLength: 40,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "SenderEmployeeNo",
                table: "notifications",
                type: "TEXT",
                maxLength: 20,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "SenderId",
                table: "notifications",
                type: "TEXT",
                maxLength: 20,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "SenderName",
                table: "notifications",
                type: "TEXT",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "TransformerId",
                table: "notifications",
                type: "TEXT",
                maxLength: 20,
                nullable: true);

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-01",
                column: "Department",
                value: "ElectricalTesting");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-02",
                column: "Department",
                value: "MaintenancePlanning");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-03",
                column: "Department",
                value: "OilLaboratory");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-04",
                column: "Department",
                value: "Management");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-05",
                column: "Department",
                value: "FieldService");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-06",
                column: "Department",
                value: "OilLaboratory");

            migrationBuilder.CreateIndex(
                name: "IX_technicians_Department",
                table: "technicians",
                column: "Department");

            migrationBuilder.CreateIndex(
                name: "IX_notifications_MessageId",
                table: "notifications",
                column: "MessageId");

            migrationBuilder.CreateIndex(
                name: "IX_notifications_SenderId",
                table: "notifications",
                column: "SenderId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_technicians_Department",
                table: "technicians");

            migrationBuilder.DropIndex(
                name: "IX_notifications_MessageId",
                table: "notifications");

            migrationBuilder.DropIndex(
                name: "IX_notifications_SenderId",
                table: "notifications");

            migrationBuilder.DropColumn(
                name: "Department",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "MessageId",
                table: "notifications");

            migrationBuilder.DropColumn(
                name: "SenderEmployeeNo",
                table: "notifications");

            migrationBuilder.DropColumn(
                name: "SenderId",
                table: "notifications");

            migrationBuilder.DropColumn(
                name: "SenderName",
                table: "notifications");

            migrationBuilder.DropColumn(
                name: "TransformerId",
                table: "notifications");

            migrationBuilder.AlterColumn<string>(
                name: "WorkOrderId",
                table: "notifications",
                type: "TEXT",
                maxLength: 40,
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "TEXT",
                oldMaxLength: 40,
                oldNullable: true);
        }
    }
}
