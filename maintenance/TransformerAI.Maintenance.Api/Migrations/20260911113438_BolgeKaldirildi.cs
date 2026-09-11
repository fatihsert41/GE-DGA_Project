using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class BolgeKaldirildi : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "Region",
                table: "technicians");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "Region",
                table: "technicians",
                type: "TEXT",
                maxLength: 50,
                nullable: false,
                defaultValue: "");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-01",
                column: "Region",
                value: "Marmara");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-02",
                column: "Region",
                value: "Marmara");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-03",
                column: "Region",
                value: "Marmara");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-04",
                column: "Region",
                value: "Ege");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-05",
                column: "Region",
                value: "İç Anadolu");

            migrationBuilder.UpdateData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-06",
                column: "Region",
                value: "Akdeniz");
        }
    }
}
