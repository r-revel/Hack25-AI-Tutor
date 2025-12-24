using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Logging;

namespace AiRepetitor.Services;

public sealed class BackendApi
{
    private readonly HttpClient _http;
    private readonly ILogger<BackendApi> _logger;
    private readonly UserManager<IdentityUser> _userManager;
    private readonly IHttpContextAccessor _httpContextAccessor;

    private const string FastApiLoginProvider = "FastApi";
    private const string FastApiTokenName = "access_token";

    public BackendApi(
        IHttpClientFactory f,
        ILogger<BackendApi> logger,
        UserManager<IdentityUser> userManager,
        IHttpContextAccessor httpContextAccessor)
    {
        _http = f.CreateClient("Backend");
        _logger = logger;
        _userManager = userManager;
        _httpContextAccessor = httpContextAccessor;
    }

    // ===== AUTH (FastAPI /login) =====
    public async Task<TokenDto?> LoginAsync(string username, string password, CancellationToken ct = default)
    {
        var payload = new { username, password };
        var resp = await _http.PostAsJsonAsync("/login", payload, ct);

        if (!resp.IsSuccessStatusCode)
        {
            var body = await resp.Content.ReadAsStringAsync(ct);
            _logger.LogWarning("Backend login failed: {Status}. Body: {Body}", resp.StatusCode, body);
            return null;
        }

        var token = await resp.Content.ReadFromJsonAsync<TokenDto>(cancellationToken: ct);
        if (token?.access_token is null)
        {
            _logger.LogWarning("Backend login: no access_token");
            return null;
        }

        return token;
    }

    // ===== helpers =====
    private void SetBearer(string jwt)
    {
        _http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", jwt);
    }

    private static InvalidOperationException NoJwt() =>
        new("No FastAPI JWT found for current user. User is not logged into FastAPI backend.");

    /// <summary>
    /// Пытаемся достать JWT сначала из claims (если оставишь), потом из Identity token store.
    /// Работает даже если claim backend_jwt отсутствует/не сериализовался в cookie.
    /// </summary>
    private async Task<bool> TryUseUserJwtAsync(ClaimsPrincipal? principal, CancellationToken ct = default)
{
    var fromClaim = principal?.FindFirst("backend_jwt")?.Value;
    if (!string.IsNullOrWhiteSpace(fromClaim))
    {
        _logger.LogInformation("JWT found in claim backend_jwt. len={Len}", fromClaim.Length);
        SetBearer(fromClaim);
        return true;
    }

    principal ??= _httpContextAccessor.HttpContext?.User;

    _logger.LogInformation("TryUseUserJwt: isAuth={Auth} name={Name}",
        principal?.Identity?.IsAuthenticated == true,
        principal?.Identity?.Name ?? "(null)");

    if (principal?.Identity?.IsAuthenticated != true)
        return false;

    var identityUser = await _userManager.GetUserAsync(principal);
    _logger.LogInformation("IdentityUser resolved: {Id}", identityUser?.Id ?? "(null)");

    if (identityUser is null)
        return false;

    var jwt = await _userManager.GetAuthenticationTokenAsync(identityUser, FastApiLoginProvider, FastApiTokenName);

    _logger.LogInformation("TokenStore read: {HasJwt} len={Len}",
        !string.IsNullOrWhiteSpace(jwt),
        jwt?.Length ?? 0);

    if (string.IsNullOrWhiteSpace(jwt))
        return false;

    SetBearer(jwt);
    return true;
}


    // ===== TOPICS (публичные) =====
    public async Task<IReadOnlyList<TopicResponseDto>> GetTopicsAsync(CancellationToken ct = default)
    {
        var topics = await _http.GetFromJsonAsync<List<TopicResponseDto>>("/topics", ct);
        return topics ?? new List<TopicResponseDto>();
    }

    public async Task<TopicResponseDto?> GetTopicAsync(int topicId, CancellationToken ct = default)
        => await _http.GetFromJsonAsync<TopicResponseDto>($"/topics/{topicId}", ct);

    // ===== TESTS =====
    public async Task<TestSessionResponseDto?> StartTestAsync(int topicId, ClaimsPrincipal user, CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();

        var resp = await _http.PostAsync($"/topics/{topicId}/start-test", content: null, ct);
        if (!resp.IsSuccessStatusCode)
        {
            var body = await resp.Content.ReadAsStringAsync(ct);
            _logger.LogWarning("StartTest failed: {Status}. Body: {Body}", resp.StatusCode, body);
            return null;
        }

        return await resp.Content.ReadFromJsonAsync<TestSessionResponseDto>(cancellationToken: ct);
    }

    public async Task<IReadOnlyList<QuestionResponseDto>> GetTestQuestionsAsync(
        int sessionId,
        ClaimsPrincipal user,
        CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();

        var resp = await _http.GetAsync($"/test/{sessionId}/questions", ct);
        resp.EnsureSuccessStatusCode();

        var questions = await resp.Content.ReadFromJsonAsync<List<QuestionResponseDto>>(cancellationToken: ct);
        return questions ?? new List<QuestionResponseDto>();
    }

    public async Task<TestResultResponseDto?> SubmitTestAsync(
        int sessionId,
        TestSubmitDto submit,
        ClaimsPrincipal user,
        CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();

        var resp = await _http.PostAsJsonAsync($"/test/{sessionId}/submit", submit, ct);
        if (!resp.IsSuccessStatusCode) return null;

        return await resp.Content.ReadFromJsonAsync<TestResultResponseDto>(cancellationToken: ct);
    }

    // ===== TEST HISTORY (защищён) =====
    public async Task<IReadOnlyList<TestSessionResponseDto>> GetTestHistoryAsync(
        ClaimsPrincipal user,
        int skip = 0,
        int limit = 20,
        CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();

        var url = $"/test/history?skip={skip}&limit={limit}";
        var resp = await _http.GetAsync(url, ct);
        resp.EnsureSuccessStatusCode();

        var tests = await resp.Content.ReadFromJsonAsync<List<TestSessionResponseDto>>(cancellationToken: ct);
        return tests ?? new List<TestSessionResponseDto>();
    }

    // ===== PROGRESS (защищён) =====
    public async Task<IReadOnlyList<UserProgressResponseDto>> GetTopicProgressAsync(
        int topicId,
        ClaimsPrincipal user,
        CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();

        var resp = await _http.GetAsync($"/topics/{topicId}/progress", ct);
        resp.EnsureSuccessStatusCode();

        var data = await resp.Content.ReadFromJsonAsync<List<UserProgressResponseDto>>(cancellationToken: ct);
        return data ?? new List<UserProgressResponseDto>();
    }

    public async Task<IReadOnlyList<UserProgressResponseDto>> SendTopicMessageAsync(
        int topicId,
        string message,
        ClaimsPrincipal user,
        CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();
        var userId = user.Identity; 
        
        var payload = new { message, is_user = true, topic_id = topicId };
        var resp = await _http.PostAsJsonAsync($"/topics/{topicId}/progress", payload, ct);
        resp.EnsureSuccessStatusCode();

        var data = await resp.Content.ReadFromJsonAsync<List<UserProgressResponseDto>>(cancellationToken: ct);
        return data ?? new List<UserProgressResponseDto>();
    }

    // ===== ADMIN =====
    public async Task<TopicResponseDto?> CreateTopicAsync(
        TopicCreateDto topicCreateDto,
        ClaimsPrincipal user,
        CancellationToken ct = default)
    {
        if (!await TryUseUserJwtAsync(user, ct))
            throw NoJwt();

        var response = await _http.PostAsJsonAsync("/admin/topics", topicCreateDto, ct);
if (!response.IsSuccessStatusCode)
{
    var body = await response.Content.ReadAsStringAsync(ct);
    _logger.LogWarning("CreateTopic failed: {Status}. Body: {Body}", response.StatusCode, body);
    return null;
}

        return await response.Content.ReadFromJsonAsync<TopicResponseDto>(cancellationToken: ct);
    }

    // ===== CHAT (публичный) =====
    public async Task<string> ChatAsync(
        string model,
        IReadOnlyList<ChatMessage> messages,
        CancellationToken ct = default)
    {
        var payload = new
        {
            model,
            stream = false,
            options = new Dictionary<string, object>(),
            messages = messages.Select(m => new
            {
                role = m.Role.ToString().ToLowerInvariant(),
                content = m.Text
            }).ToList()
        };

        var resp = await _http.PostAsJsonAsync("/api/chat", payload, ct);
        resp.EnsureSuccessStatusCode();

        var json = await resp.Content.ReadFromJsonAsync<OllamaChatResponse>(cancellationToken: ct);
        return json?.message?.content ?? "";
    }

    public async Task<bool> RegisterAsync(string username, string email, string password, CancellationToken ct = default)
    {
        var payload = new { username, email, password };
        var resp = await _http.PostAsJsonAsync("/register", payload, ct);
        if (!resp.IsSuccessStatusCode)
        {
            var body = await resp.Content.ReadAsStringAsync(ct);
            _logger.LogWarning("Backend register failed: {Status}. Body: {Body}", resp.StatusCode, body);
            return false;
        }
        return true;
    }

    // ===== internal types for /api/chat response =====
    private sealed class OllamaChatResponse
    {
        public string? model { get; set; }
        public OllamaMessage? message { get; set; }
        public bool done { get; set; }
    }

    private sealed class OllamaMessage
    {
        public string? role { get; set; }
        public string? content { get; set; }
    }
}
