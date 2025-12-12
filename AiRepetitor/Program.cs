using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.VectorData;
using AiRepetitor.Components;
using AiRepetitor.Services;
using AiRepetitor.Services.Ingestion;
using OllamaSharp;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddRazorComponents().AddInteractiveServerComponents();

// 1) ≈сли Blazor запускать на винде, а backend+ollama в Docker с проброшенными портами:
var backendBaseUrl_Host = "http://localhost:8000";
var ollamaBaseUrl_Host = "http://localhost:11434";

// 2) ≈сли Blazor запускать ¬ DOCKER COMPOSE (как сервис), а backend и ollama тоже в compose:
var backendBaseUrl_Docker = "http://backend:8000";
var ollamaBaseUrl_Docker = "http://ollama:11434";


// ¬ыбор по окружению: Development => запуск на хосте, иначе => в docker
// (если ты запускаешь Blazor в docker, выставл€й ASPNETCORE_ENVIRONMENT=Production или Staging)
var backendBaseUrl = builder.Environment.IsDevelopment()
    ? backendBaseUrl_Host
    : backendBaseUrl_Docker;

var ollamaBaseUrl = builder.Environment.IsDevelopment()
    ? ollamaBaseUrl_Host
    : ollamaBaseUrl_Docker;


var ollamaUri = new Uri(ollamaBaseUrl);


IChatClient chatClient = new OllamaApiClient(ollamaUri, "qwen2.5:1.5b");
IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator =
    new OllamaApiClient(ollamaUri, "nomic-embed-text");

builder.Services.AddHttpClient("Backend", c =>
{
    c.BaseAddress = new Uri(backendBaseUrl);
});

var vectorStore = new JsonVectorStore(Path.Combine(AppContext.BaseDirectory, "vector-store"));

builder.Services.AddSingleton<IVectorStore>(vectorStore);
builder.Services.AddScoped<DataIngestor>();
builder.Services.AddScoped<BackendApi>();
builder.Services.AddSingleton<SemanticSearch>();

builder.Services.AddChatClient(chatClient).UseFunctionInvocation().UseLogging();
builder.Services.AddEmbeddingGenerator(embeddingGenerator);

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

