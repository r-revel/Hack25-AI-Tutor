// Program.cs
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.VectorData;
using AiRepetitor.Components;
using AiRepetitor.Services;
using AiRepetitor.Services.Ingestion;
using OllamaSharp;
using DotNetEnv;

using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.AspNetCore.Components.Authorization;
using AiRepetitor.Data;

var builder = WebApplication.CreateBuilder(args);

// Razor + interactive Blazor Server
builder.Services.AddRazorComponents()
                .AddInteractiveServerComponents();

// Подхватываем .env если есть
Env.Load();


// ==== читаем конфиги из env ====
var backendBaseUrl = Environment.GetEnvironmentVariable("BACKEND_URL");
var ollamaBaseUrl  = Environment.GetEnvironmentVariable("OLLAMA_URL");
var chatModel      = Environment.GetEnvironmentVariable("MODEL_OLLAMA_CHAT");
var embedModel     = Environment.GetEnvironmentVariable("MODEL_OLLAMA_EMBEDDING");

Console.WriteLine($"BACKEND_URL={backendBaseUrl}");
Console.WriteLine($"OLLAMA_URL={ollamaBaseUrl}");
Console.WriteLine($"CHAT_MODEL={chatModel}");
Console.WriteLine($"EMBED_MODEL={embedModel}");


// ==== проверяем обязательные переменные ====
if (string.IsNullOrWhiteSpace(ollamaBaseUrl))
    throw new InvalidOperationException("OLLAMA_URL is not set");

if (string.IsNullOrWhiteSpace(chatModel))
    throw new InvalidOperationException("MODEL_OLLAMA_CHAT is not set");

if (string.IsNullOrWhiteSpace(embedModel))
    throw new InvalidOperationException("MODEL_OLLAMA_EMBEDDING is not set");


// ==== Ollama ====
var ollamaUri = new Uri(ollamaBaseUrl);

IChatClient chatClient = new OllamaApiClient(ollamaUri, chatModel);
IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator =
        new OllamaApiClient(ollamaUri, embedModel);

builder.Services.AddSingleton(chatClient);
builder.Services.AddSingleton(embeddingGenerator);


// ==== HTTP-клиенты ====
builder.Services.AddHttpClient();           // фабрика всегда есть

if (!string.IsNullOrWhiteSpace(backendBaseUrl))
{
    builder.Services.AddHttpClient("Backend", client =>
    {
        client.BaseAddress = new Uri(backendBaseUrl);
    });

    builder.Services.AddScoped<BackendApi>();  // регистрируем API только если реально есть backend URL
}


// ==== Векторное хранилище ====
var vectorStore = new JsonVectorStore(Path.Combine(AppContext.BaseDirectory, "vector-store"));
builder.Services.AddSingleton<IVectorStore>(vectorStore);

builder.Services.AddScoped<DataIngestor>();
builder.Services.AddSingleton<SemanticSearch>();


// ==== кеш загрузок ====
builder.Services.AddDbContext<IngestionCacheDbContext>(options =>
    options.UseSqlite("Data Source=ingestioncache.db"));


// ==== Auth (Identity) ====
builder.Services.AddDbContext<AuthDbContext>(options =>
    options.UseSqlite("Data Source=auth.db"));

builder.Services
    .AddIdentityCore<IdentityUser>(options =>
    {
        // Упростим пароль для теста
        options.Password.RequireDigit = false;
        options.Password.RequireLowercase = false;
        options.Password.RequireNonAlphanumeric = false;
        options.Password.RequireUppercase = false;
        options.Password.RequiredLength = 6;

        // То, что тебе нужно сейчас:
        options.SignIn.RequireConfirmedAccount = false;
    })
    .AddEntityFrameworkStores<AuthDbContext>()
    .AddSignInManager();

// Cookie-аутентификация для Blazor Server
builder.Services
    .AddAuthentication(options =>
    {
        options.DefaultScheme = IdentityConstants.ApplicationScheme;
        options.DefaultSignInScheme = IdentityConstants.ApplicationScheme;
    })
    .AddIdentityCookies();

// Авторизация + проброс AuthenticationState в компоненты
builder.Services.AddAuthorization();
builder.Services.AddCascadingAuthenticationState();

// ==== BUILD ====
var app = builder.Build();
IngestionCacheDbContext.Initialize(app.Services);


// ==== PIPELINE ====
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseAntiforgery();
app.UseStaticFiles();

app.UseAuthentication();
app.UseAuthorization();

app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();


// ==== тихо загружаем PDF при старте ====
try
{
    await DataIngestor.IngestDataAsync(
        app.Services,
        new PDFDirectorySource(Path.Combine(builder.Environment.WebRootPath, "Data"))
    );

    app.Logger.LogInformation("PDF ingestion completed");
}
catch (Exception ex)
{
    app.Logger.LogError(ex, "Failed to ingest PDF data at startup");
}


// ==== debug endpoint ====
app.MapGet("/debug/where", () => new
{
    env = app.Environment.EnvironmentName,
    backendBaseUrl,
    ollamaBaseUrl,
    chatModel,
    embedModel
});

app.Logger.LogInformation("Backend API URL = {BackendURL}", backendBaseUrl);
app.Logger.LogInformation("Ollama URL = {OllamaURL}", ollamaBaseUrl);

app.Run();
