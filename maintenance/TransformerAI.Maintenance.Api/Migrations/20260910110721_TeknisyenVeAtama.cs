using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class TeknisyenVeAtama : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "AssignedTo",
                table: "work_orders");

            migrationBuilder.AddColumn<string>(
                name: "TechnicianId",
                table: "work_orders",
                type: "TEXT",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "technicians",
                columns: table => new
                {
                    Id = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    Region = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Specialty = table.Column<string>(type: "TEXT", maxLength: 20, nullable: false),
                    MaxOpenOrders = table.Column<int>(type: "INTEGER", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_technicians", x => x.Id);
                });

            migrationBuilder.InsertData(
                table: "technicians",
                columns: new[] { "Id", "IsActive", "MaxOpenOrders", "Name", "Region", "Specialty" },
                values: new object[,]
                {
                    { "TK-01", true, 3, "Ahmet Yılmaz", "Marmara", "Electrical" },
                    { "TK-02", true, 3, "Elif Demir", "Marmara", "Thermal" },
                    { "TK-03", true, 5, "Mehmet Kaya", "Marmara", "Sampling" },
                    { "TK-04", true, 4, "Zeynep Şahin", "Ege", "General" },
                    { "TK-05", true, 4, "Burak Aydın", "İç Anadolu", "General" },
                    { "TK-06", true, 4, "Selin Öztürk", "Akdeniz", "Sampling" }
                });

            migrationBuilder.CreateIndex(
                name: "IX_work_orders_TechnicianId",
                table: "work_orders",
                column: "TechnicianId");

            migrationBuilder.AddForeignKey(
                name: "FK_work_orders_technicians_TechnicianId",
                table: "work_orders",
                column: "TechnicianId",
                principalTable: "technicians",
                principalColumn: "Id",
                onDelete: ReferentialAction.SetNull);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_work_orders_technicians_TechnicianId",
                table: "work_orders");

            migrationBuilder.DropTable(
                name: "technicians");

            migrationBuilder.DropIndex(
                name: "IX_work_orders_TechnicianId",
                table: "work_orders");

            migrationBuilder.DropColumn(
                name: "TechnicianId",
                table: "work_orders");

            migrationBuilder.AddColumn<string>(
                name: "AssignedTo",
                table: "work_orders",
                type: "TEXT",
                maxLength: 100,
                nullable: true);
        }
    }
}
