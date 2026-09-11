using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class SicilVeRol : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "EmployeeNo",
                table: "technicians",
                type: "TEXT",
                maxLength: 20,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "Role",
                table: "technicians",
                type: "TEXT",
                maxLength: 20,
                nullable: false,
                defaultValue: "");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-01",
                columns: new[] { "EmployeeNo", "Role" },
                values: new object[] { "10247", "Technician" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-02",
                columns: new[] { "EmployeeNo", "Role" },
                values: new object[] { "10318", "Engineer" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-03",
                columns: new[] { "EmployeeNo", "Role" },
                values: new object[] { "10455", "Technician" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-04",
                columns: new[] { "EmployeeNo", "Role" },
                values: new object[] { "10502", "Supervisor" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-05",
                columns: new[] { "EmployeeNo", "Role" },
                values: new object[] { "10611", "Technician" });

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-06",
                columns: new[] { "EmployeeNo", "Role" },
                values: new object[] { "10740", "Engineer" });

            migrationBuilder.CreateIndex(
                name: "IX_technicians_EmployeeNo",
                table: "technicians",
                column: "EmployeeNo",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_technicians_EmployeeNo",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "EmployeeNo",
                table: "technicians");

            migrationBuilder.DropColumn(
                name: "Role",
                table: "technicians");
        }
    }
}
