using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.VectorData;
using AiRepetitor.Components;
using AiRepetitor.Services;
using AiRepetitor.Services.Ingestion;
using OllamaSharp;
using DotNetEnv;


using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Components.Authorization;
using AiRepetitor.Data;
using Microsoft.AspNetCore.DataProtection;
using Blazored.LocalStorage;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents()
    .AddHubOptions(options =>
    {
        options.EnableDetailedErrors = true;
    });

builder.Services
    .AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo("/root/.aspnet/DataProtection-Keys"))
    .SetApplicationName("AiRepetitor");

builder.Services.AddAntiforgery(options =>
{
    options.SuppressXFrameOptionsHeader = true;
    options.Cookie.SameSite = SameSiteMode.Lax;
});

// .env
Env.Load();

// ==== читаем конфиги из env ====
var backendBaseUrl = Environment.GetEnvironmentVariable("BACKEND_URL");
var ollamaBaseUrl  = Environment.GetEnvironmentVariable("OLLAMA_URL");

// поддерживаем и старые, и новые имена переменных
var chatModel  = Environment.GetEnvironmentVariable("MODEL_OLLAMA_CHAT")
                 ?? Environment.GetEnvironmentVariable("CHAT_MODEL");
var embedModel = Environment.GetEnvironmentVariable("MODEL_OLLAMA_EMBEDDING")
                 ?? Environment.GetEnvironmentVariable("EMBED_MODEL");

Console.WriteLine($"BACKEND_URL={backendBaseUrl}");
Console.WriteLine($"OLLAMA_URL={ollamaBaseUrl}");
Console.WriteLine($"CHAT_MODEL={chatModel}");
Console.WriteLine($"EMBED_MODEL={embedModel}");

// ==== проверки ====
if (string.IsNullOrWhiteSpace(backendBaseUrl))
    throw new InvalidOperationException("BACKEND_URL is not set");
if (string.IsNullOrWhiteSpace(ollamaBaseUrl))
    throw new InvalidOperationException("OLLAMA_URL is not set");
if (string.IsNullOrWhiteSpace(chatModel))
    throw new InvalidOperationException("MODEL_OLLAMA_CHAT / CHAT_MODEL is not set");
if (string.IsNullOrWhiteSpace(embedModel))
    throw new InvalidOperationException("MODEL_OLLAMA_EMBEDDING / EMBED_MODEL is not set");

// ==== Ollama ====
var ollamaUri = new Uri(ollamaBaseUrl);

IChatClient chatClient = new OllamaApiClient(ollamaUri, chatModel);
IEmbeddingGenerator<string, Embedding<float>> embeddingGenerator =
        new OllamaApiClient(ollamaUri, embedModel);

builder.Services.AddSingleton(chatClient);
builder.Services.AddSingleton(embeddingGenerator);

// ==== HTTP-клиенты ====
builder.Services.AddHttpClient();
builder.Services.AddHttpClient("Backend", client =>
{
    client.BaseAddress = new Uri(backendBaseUrl!);
});
builder.Services.AddScoped<BackendApi>();

// ==== Векторное хранилище ====
var vectorStore = new JsonVectorStore(Path.Combine(AppContext.BaseDirectory, "vector-store"));
builder.Services.AddSingleton<IVectorStore>(vectorStore);

builder.Services.AddScoped<DataIngestor>();
builder.Services.AddSingleton<SemanticSearch>();
builder.Services.AddBlazoredLocalStorage();


// ==== кеш загрузок ====
builder.Services.AddDbContext<IngestionCacheDbContext>(options =>
    options.UseSqlite("Data Source=ingestioncache.db"));

// ==== Auth (Identity) ====
builder.Services.AddDbContext<AuthDbContext>(options =>
    options.UseSqlite("Data Source=auth.db"));

builder.Services
    .AddIdentityCore<IdentityUser>(options =>
    {
        options.Password.RequireDigit = false;
        options.Password.RequireLowercase = false;
        options.Password.RequireNonAlphanumeric = false;
        options.Password.RequireUppercase = false;
        options.Password.RequiredLength = 6;

        options.SignIn.RequireConfirmedAccount = false;
    })
    .AddEntityFrameworkStores<AuthDbContext>()
    .AddSignInManager();

// Cookie-аутентификация
builder.Services
    .AddAuthentication(options =>
    {
        options.DefaultScheme = IdentityConstants.ApplicationScheme;
        options.DefaultSignInScheme = IdentityConstants.ApplicationScheme;
    })
    .AddIdentityCookies();

builder.Services.ConfigureApplicationCookie(options =>
{
    options.LoginPath = "/login";
    options.AccessDeniedPath = "/login";

    options.Cookie.SameSite = SameSiteMode.Lax;
    options.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
});


// Авторизация + проброс AuthenticationState в компоненты
builder.Services.AddAuthorization();
builder.Services.AddCascadingAuthenticationState();

// ==== BUILD ====
var app = builder.Build();
IngestionCacheDbContext.Initialize(app.Services);

using (var scope = app.Services.CreateScope())
{
    var authDb = scope.ServiceProvider.GetRequiredService<AuthDbContext>();
    authDb.Database.EnsureCreated();
}

// ==== PIPELINE ====
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

if (!app.Environment.IsDevelopment())
{
    app.UseHttpsRedirection();
}


app.UseStaticFiles();

app.UseAuthentication();
app.UseAuthorization();

// Для интерактивных Razor Components/форм
app.UseAntiforgery();

// === endpoints авторизации (минимальные API) ===

// POST /auth/login
app.MapPost("/auth/login", async (
    HttpContext httpContext,
    SignInManager<IdentityUser> signInManager) =>
{
    var form = await httpContext.Request.ReadFormAsync();

    var email      = form["Email"].ToString();
    var password   = form["Password"].ToString();
    var rememberMe = !string.IsNullOrEmpty(form["RememberMe"]);
    var returnUrl  = form["ReturnUrl"].ToString();

    if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
    {
        return Results.Redirect("/login?error=empty");
    }

    var result = await signInManager.PasswordSignInAsync(
        email,
        password,
        rememberMe,
        lockoutOnFailure: false);

    if (result.Succeeded)
    {
        // простая и безопасная обработка returnUrl
        if (!string.IsNullOrWhiteSpace(returnUrl) && returnUrl.StartsWith("/"))
            return Results.Redirect(returnUrl);

        return Results.Redirect("/");
    }

    return Results.Redirect("/login?error=invalid");
})
.DisableAntiforgery();


// POST /auth/register (можешь оставить на будущее или удалить, если не нужен)
app.MapPost("/auth/register", async (
    HttpContext httpContext,
    UserManager<IdentityUser> userManager,
    SignInManager<IdentityUser> signInManager) =>
{
    var form = await httpContext.Request.ReadFormAsync();

    var email           = form["Email"].ToString();
    var password        = form["Password"].ToString();
    var confirmPassword = form["ConfirmPassword"].ToString();

    if (string.IsNullOrWhiteSpace(email) ||
        string.IsNullOrWhiteSpace(password) ||
        string.IsNullOrWhiteSpace(confirmPassword))
    {
        return Results.Redirect("/register?error=empty");
    }

    if (!string.Equals(password, confirmPassword, StringComparison.Ordinal))
    {
        return Results.Redirect("/register?error=nomatch");
    }

    var user = new IdentityUser
    {
        UserName = email,
        Email = email
    };

    var createResult = await userManager.CreateAsync(user, password);

    if (!createResult.Succeeded)
    {
        return Results.Redirect("/register?error=identity");
    }

    await signInManager.SignInAsync(user, isPersistent: false);
    return Results.Redirect("/");
})
.DisableAntiforgery();

// Razor Components (чат и прочее)
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

// ==== тихо загружаем PDF при старте ====
try
{
    await DataIngestor.IngestDataAsync(
        app.Services,
        new PDFDirectorySource(Path.Combine(app.Environment.WebRootPath, "Data"))
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


// logout
app.MapPost("/logout", async (
    SignInManager<IdentityUser> signInManager,
    HttpContext httpContext) =>
{
    await signInManager.SignOutAsync();
    return Results.Redirect("/login");
})
.RequireAuthorization()
.DisableAntiforgery();

app.Logger.LogInformation("Backend API URL = {BackendURL}", backendBaseUrl);
app.Logger.LogInformation("Ollama URL = {OllamaURL}", ollamaBaseUrl);

app.Run();
