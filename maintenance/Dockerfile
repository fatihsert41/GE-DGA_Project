# TransformerAI — .NET bakım servisi (Zayıf yanlar 4/4)
#
# İki aşamalı (multi-stage) imaj:
#   1. sdk   — derler ve yayımlar (büyük: derleyici, NuGet önbelleği)
#   2. aspnet — yalnızca çalışma zamanı ve yayımlanan dosyalar (küçük)
# Son imajda derleyici ve kaynak kod YOK: daha küçük, saldırı yüzeyi dar.

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Önce proje dosyası: paket geri yükleme katmanı önbellekten gelsin.
COPY TransformerAI.Maintenance.Api/TransformerAI.Maintenance.Api.csproj TransformerAI.Maintenance.Api/
RUN dotnet restore TransformerAI.Maintenance.Api/TransformerAI.Maintenance.Api.csproj

COPY TransformerAI.Maintenance.Api/ TransformerAI.Maintenance.Api/
RUN dotnet publish TransformerAI.Maintenance.Api/TransformerAI.Maintenance.Api.csproj \
    -c Release -o /out --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /out .

# Production: imza anahtarı ZORUNLU (compose .env'den verir). Anahtarsız
# container açılmayı reddeder — güvenlik sertleştirmesinin amacı bu.
ENV ASPNETCORE_ENVIRONMENT=Production \
    ASPNETCORE_URLS=http://+:5080 \
    ConnectionStrings__Maintenance="Data Source=/data/maintenance.db" \
    MlService__BaseUrl=http://backend:8000

EXPOSE 5080
ENTRYPOINT ["dotnet", "TransformerAI.Maintenance.Api.dll"]
