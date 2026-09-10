using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TransformerAI.Maintenance.Api.Migrations
{
    /// <inheritdoc />
    public partial class SiraNumarasiVeGecisKurallari : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "CompletionNote",
                table: "work_orders",
                type: "TEXT",
                maxLength: 1000,
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "Seq",
                table: "work_orders",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            // Mevcut kayıtların sıra numarasını kimlikten doldur:
            // "WO-0007" -> 7. Bu olmadan hepsi 0 kalır ve tekil indeks
            // ikinci kaydı reddeder.
            migrationBuilder.Sql(
                "UPDATE work_orders SET Seq = CAST(SUBSTR(Id, 4) AS INTEGER)");

            migrationBuilder.CreateIndex(
                name: "IX_work_orders_Seq",
                table: "work_orders",
                column: "Seq",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_work_orders_Seq",
                table: "work_orders");

            migrationBuilder.DropColumn(
                name: "CompletionNote",
                table: "work_orders");

            migrationBuilder.DropColumn(
                name: "Seq",
                table: "work_orders");
        }
    }
}
