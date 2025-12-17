using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.VectorData;
using AiRepetitor.Components;
using AiRepetitor.Services;
using AiRepetitor.Services.Ingestion;
using OllamaSharp;
using DotNetEnv;
using System.Diagnostics; // Добавьте эту строку

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddRazorComponents().AddInteractiveServerComponents();

// Загрузите переменные из .env файла (добавьте в самом начале)
Env.Load(); // Загружает из .env в корне проекта


var backendBaseUrl = Environment.GetEnvironmentVariable("BACKEND_URL");
var ollamaBaseUrl = Environment.GetEnvironmentVariable("OLLAMA_URL");

// Логирование для отладки (лучше использовать ILogger)
Console.WriteLine($"BACKEND_URL: {backendBaseUrl}");
Console.WriteLine($"OLLAMA_URL: {ollamaBaseUrl}");

var ollamaUri = new Uri(ollamaBaseUrl);


IChatClient chatClient = new OllamaApiClient(ollamaUri, Environment.GetEnvironmentVariable("MODEL_OLLAMA_CHAT"));
IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator =
    new OllamaApiClient(ollamaUri, Environment.GetEnvironmentVariable("MODEL_OLLAMA_EMBEDDING"));

// Регистрируем в DI контейнере (ДОБАВЬТЕ ЭТИ СТРОКИ!)
builder.Services.AddSingleton(chatClient);
builder.Services.AddSingleton(embeddingGenerator);

builder.Services.AddHttpClient("Backend", c =>
{
    c.BaseAddress = new Uri(backendBaseUrl);
});

var vectorStore = new JsonVectorStore(Path.Combine(AppContext.BaseDirectory, "vector-store"));

builder.Services.AddSingleton<IVectorStore>(vectorStore);
builder.Services.AddScoped<DataIngestor>();
builder.Services.AddScoped<BackendApi>();
builder.Services.AddSingleton<SemanticSearch>();

// builder.Services.AddChatClient(chatClient).UseFunctionInvocation().UseLogging();
// builder.Services.AddEmbeddingGenerator(embeddingGenerator);

builder.Services.AddDbContext<IngestionCacheDbContext>(options =>
    options.UseSqlite("Data Source=ingestioncache.db"));

var app = builder.Build();
IngestionCacheDbContext.Initialize(app.Services);

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseAntiforgery();

app.UseStaticFiles();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

// Ingest PDF from /wwwroot/Data
await DataIngestor.IngestDataAsync(
    app.Services,
    new PDFDirectorySource(Path.Combine(builder.Environment.WebRootPath, "Data")));

app.Logger.LogInformation("Backend API URL = {Url}", backendBaseUrl);
app.Logger.LogInformation("Ollama URL = {Url}", ollamaBaseUrl);

app.MapGet("/debug/where", () => new
{
    env = app.Environment.EnvironmentName,
    backendBaseUrl,
    ollamaBaseUrl
});

app.Run();

