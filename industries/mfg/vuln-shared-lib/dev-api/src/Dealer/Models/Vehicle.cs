namespace Dealer.Models;

public sealed class Vehicle
{
    public string Vin { get; set; } = "";
    public string DealerId { get; set; } = "";
    public string Model { get; set; } = "";
    public int Year { get; set; }
    public string Status { get; set; } = "";
    public long PriceCents { get; set; }
    public string ImageUrl { get; set; } = "";
    public int DaysInStock { get; set; }
}

public sealed record InventoryItem(string Vin, string Model, int Year, string Status, long PriceCents, string ImageUrl)
{
    public static InventoryItem From(Vehicle vehicle) =>
        new(vehicle.Vin, vehicle.Model, vehicle.Year, vehicle.Status, vehicle.PriceCents, vehicle.ImageUrl);
}

public sealed record StickerModel(Vehicle Vehicle, string Note);
public sealed record BulletinRow(string Vin, long PriceCents);
public sealed record ExportRequest(string FileName);
