using System.Security.Claims;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.VectorData;
using AiRepetitor.Components;
using AiRepetitor.Data;
using AiRepetitor.Services;
using AiRepetitor.Services.Ingestion;
using Blazored.LocalStorage;
using DotNetEnv;
using OllamaSharp;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents()
    .AddHubOptions(options => { options.EnableDetailedErrors = true; });


var DataKey = Environment.GetEnvironmentVariable("DIR_KAY");

if (string.IsNullOrEmpty(DataKey))
{
    DataKey = "/root/.aspnet/DataProtection-Keys";
}


builder.Services
    .AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo(DataKey))
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
var ollamaBaseUrl = Environment.GetEnvironmentVariable("OLLAMA_URL");

var chatModel = Environment.GetEnvironmentVariable("MODEL_OLLAMA_CHAT")
               ?? Environment.GetEnvironmentVariable("CHAT_MODEL");
var embedModel = Environment.GetEnvironmentVariable("MODEL_OLLAMA_EMBEDDING")
               ?? Environment.GetEnvironmentVariable("EMBED_MODEL");

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
    client.BaseAddress = new Uri(backendBaseUrl);
})
.ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
{
    UseCookies = true,
    CookieContainer = new System.Net.CookieContainer()
});

builder.Services.AddHttpContextAccessor();
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
// Важно: AddIdentity (не AddIdentityCore) -> чтобы был token store (AspNetUserTokens)
builder.Services.AddDbContext<AuthDbContext>(options =>
    options.UseSqlite("Data Source=auth.db"));

builder.Services
    .AddIdentity<IdentityUser, IdentityRole>(options =>
    {
        options.Password.RequireDigit = false;
        options.Password.RequireLowercase = false;
        options.Password.RequireNonAlphanumeric = false;
        options.Password.RequireUppercase = false;
        options.Password.RequiredLength = 4;

        options.SignIn.RequireConfirmedAccount = false;
    })
    .AddEntityFrameworkStores<AuthDbContext>()
    .AddDefaultTokenProviders();

builder.Services.ConfigureApplicationCookie(options =>
{
    options.LoginPath = "/login";
    options.AccessDeniedPath = "/login";

    options.Cookie.SameSite = SameSiteMode.Lax;
    options.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
});

builder.Services.AddAuthorization();
builder.Services.AddCascadingAuthenticationState();

// ==== BUILD ====
var app = builder.Build();
IngestionCacheDbContext.Initialize(app.Services);

using (var scope = app.Services.CreateScope())
{
    var authDb = scope.ServiceProvider.GetRequiredService<AuthDbContext>();
    authDb.Database.EnsureCreated();

    // Seed Identity user (ruslan)
    var userManager = scope.ServiceProvider.GetRequiredService<UserManager<IdentityUser>>();

    var seedUsername = Environment.GetEnvironmentVariable("SEED_USER_USERNAME") ?? "ruslan";
    var seedEmail = Environment.GetEnvironmentVariable("SEED_USER_EMAIL") ?? "ruslan@example.com";
    var seedPassword = Environment.GetEnvironmentVariable("SEED_USER_PASSWORD") ?? "1234";

    var existing = await userManager.FindByNameAsync(seedUsername);
    if (existing == null)
    {
        var u = new IdentityUser
        {
            UserName = seedUsername,
            Email = seedEmail
        };

        var res = await userManager.CreateAsync(u, seedPassword);
        if (!res.Succeeded)
        {
            app.Logger.LogError("Failed to seed Identity user: {Errors}",
                string.Join("; ", res.Errors.Select(e => e.Description)));
        }
        else
        {
            app.Logger.LogInformation("✅ Seed Identity user created: {User}", seedUsername);
        }
    }
    else
    {
        app.Logger.LogInformation("ℹ️ Seed Identity user already exists: {User}", seedUsername);
    }
}

// ==== PIPELINE ====
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
    app.UseHttpsRedirection();
}

app.UseStaticFiles();

app.UseAuthentication();
app.UseAuthorization();

// Для интерактивных Razor Components/форм
app.UseAntiforgery();

// =============================
// POST /auth/login
// =============================
app.MapPost("/auth/login", async (
    HttpContext httpContext,
    UserManager<IdentityUser> userManager,
    SignInManager<IdentityUser> signInManager,
    BackendApi backendApi) =>
{
    var form = await httpContext.Request.ReadFormAsync();

    var username = form["Username"].ToString();
    var password = form["Password"].ToString();
    var rememberMe = !string.IsNullOrEmpty(form["RememberMe"]);
    var returnUrl = form["ReturnUrl"].ToString();

    if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password))
        return Results.Redirect("/login?error=empty");

    // 1) ищем Identity по username
    var user = await userManager.FindByNameAsync(username);
    if (user is null)
        return Results.Redirect("/login?error=invalid");

    var okPassword = await userManager.CheckPasswordAsync(user, password);
    if (!okPassword)
        return Results.Redirect("/login?error=invalid");

    // 2) логинимся в FastAPI по username/password
    var token = await backendApi.LoginAsync(username, password);
    if (token?.access_token is null)
    {
        app.Logger.LogWarning("FastAPI login failed for {Username}", username);
        return Results.Redirect("/login?error=backend");
    }

    // 3) логинимся в Identity (cookie)
    await signInManager.SignInAsync(user, rememberMe);

    // 4) сохраняем JWT в Identity token store (AspNetUserTokens)
    await userManager.SetAuthenticationTokenAsync(
        user,
        loginProvider: "FastApi",
        tokenName: "access_token",
        tokenValue: token.access_token);

    app.Logger.LogInformation("✅ Stored FastAPI JWT for {User}. jwtLen={Len}", username, token.access_token.Length);

    if (!string.IsNullOrWhiteSpace(returnUrl) && returnUrl.StartsWith("/"))
        return Results.Redirect(returnUrl);

    return Results.Redirect("/");
})
.DisableAntiforgery();

// =============================
// POST /auth/register
// =============================
app.MapPost("/auth/register", async (
    HttpContext httpContext,
    UserManager<IdentityUser> userManager,
    SignInManager<IdentityUser> signInManager,
    BackendApi backendApi) =>
{
    var form = await httpContext.Request.ReadFormAsync();

    var username = form["Username"].ToString();
    var email = form["Email"].ToString();
    var password = form["Password"].ToString();
    var confirmPassword = form["ConfirmPassword"].ToString();

    if (string.IsNullOrWhiteSpace(username) ||
        string.IsNullOrWhiteSpace(email) ||
        string.IsNullOrWhiteSpace(password) ||
        string.IsNullOrWhiteSpace(confirmPassword))
    {
        return Results.Redirect("/register?error=empty");
    }

    if (!string.Equals(password, confirmPassword, StringComparison.Ordinal))
        return Results.Redirect("/register?error=nomatch");

    // 1) регистрируем в FastAPI
    var okBackend = await backendApi.RegisterAsync(username, email, password);
    if (!okBackend)
        return Results.Redirect("/register?error=backend");

    // 2) регистрируем в Identity
    var user = new IdentityUser
    {
        UserName = username,
        Email = email
    };

    var createResult = await userManager.CreateAsync(user, password);
    if (!createResult.Succeeded)
    {
        var msg = string.Join(" | ", createResult.Errors.Select(e => e.Description));
        app.Logger.LogWarning("Identity register failed for {User}. Errors: {Errors}", username, msg);

        var encoded = Uri.EscapeDataString(msg);
        return Results.Redirect($"/register?error=identity&msg={encoded}");
    }

    // ✅ вот этого у тебя не хватает
    await signInManager.SignInAsync(user, isPersistent: false);
    return Results.Redirect("/");
})
.DisableAntiforgery();

// Razor Components
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

// ==== debug endpoints ====
app.MapGet("/debug/where", () => new
{
    env = app.Environment.EnvironmentName,
    backendBaseUrl,
    ollamaBaseUrl,
    chatModel,
    embedModel
});

app.MapGet("/debug/whoami", (HttpContext ctx) =>
{
    var u = ctx.User;
    return Results.Json(new
    {
        isAuth = u?.Identity?.IsAuthenticated ?? false,
        name = u?.Identity?.Name,
        claims = u?.Claims.Select(c => new { c.Type, c.Value }).ToList()
    });
});

// logout
app.MapPost("/logout", async (SignInManager<IdentityUser> signInManager) =>
{
    await signInManager.SignOutAsync();
    return Results.Redirect("/login");
})
.RequireAuthorization()
.DisableAntiforgery();

app.Logger.LogInformation("Backend API URL = {BackendURL}", backendBaseUrl);
app.Logger.LogInformation("Ollama URL = {OllamaURL}", ollamaBaseUrl);

app.Run();
