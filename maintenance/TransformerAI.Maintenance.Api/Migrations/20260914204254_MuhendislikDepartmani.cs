using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class MuhendislikDepartmani : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.InsertData(
                table: "technicians",
                columns: new[] { "Id", "Department", "EmployeeNo", "FailedAttempts", "IsActive", "LockedUntil", "MaxOpenOrders", "Name", "PinHash", "PinSalt", "Role", "Specialty" },
                values: new object[,]
                {
                    { "TK-07", "Engineering", "10833", 0, true, null, 2, "Deniz Koç", "", "", "Engineer", "Electrical" },
                    { "TK-08", "Engineering", "10921", 0, true, null, 2, "Can Yıldız", "", "", "Engineer", "Thermal" }
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DeleteData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-07");

            migrationBuilder.DeleteData(
                table: "technicians",
                keyColumn: "Id",
                keyValue: "TK-08");
        }
    }
}
