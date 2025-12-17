#./AiRepetitor/Dockerfile
FROM mcr.microsoft.com/dotnet/sdk:9.0-alpine AS build
WORKDIR /src

# 1) Копируем csproj и NuGet.Config заранее (чтобы работал docker layer cache)
COPY AiRepetitor.csproj ./
COPY NuGet.Config ./

# 2) Restore строго с этим конфигом + на всякий случай обнуляем fallback
RUN dotnet restore AiRepetitor.csproj \
    --configfile NuGet.Config \
    --disable-parallel \
    /p:RestoreFallbackFolders=

# 3) Копируем остальной код
COPY . ./

# 4) Publish без restore
RUN dotnet publish AiRepetitor.csproj -c Release -o /app/publish \
    --self-contained false \
    --no-restore \
    /p:RestoreFallbackFolders= \
    -p:PublishTrimmed=false \
    -p:PublishSingleFile=false

FROM mcr.microsoft.com/dotnet/aspnet:9.0-alpine
WORKDIR /app

RUN apk add --no-cache icu-libs curl

ENV ASPNETCORE_URLS=http://+:8090
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false
ENV DOTNET_RUNNING_IN_CONTAINER=true
ENV ASPNETCORE_ENVIRONMENT=Development

EXPOSE 8090
COPY --from=build /app/publish .

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8090/health || exit 1

ENTRYPOINT ["dotnet", "AiRepetitor.dll"]
