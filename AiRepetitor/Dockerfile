FROM mcr.microsoft.com/dotnet/sdk:9.0-alpine AS build
WORKDIR /src

# 1) Копируем csproj и NuGet.Config заранее
COPY AiRepetitor.csproj ./
COPY NuGet.Config ./

# 2) Restore
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

RUN apk add --no-cache icu-libs curl bash

ENV ASPNETCORE_URLS=http://+:8090
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false
ENV DOTNET_RUNNING_IN_CONTAINER=true
ENV ASPNETCORE_ENVIRONMENT=Development

EXPOSE 8090

# Копируем публикацию
COPY --from=build /app/publish .

# Копируем скрипт и делаем его исполняемым
COPY start-web.sh ./
RUN chmod +x ./start-web.sh

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8090/health || exit 1

# Запуск через скрипт
ENTRYPOINT ["./start-web.sh"]
