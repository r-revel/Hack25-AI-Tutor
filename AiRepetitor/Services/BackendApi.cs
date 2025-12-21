using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using Microsoft.Extensions.AI;

namespace AiRepetitor.Services;

public sealed class BackendApi
{
    private readonly HttpClient _http;
    private readonly ILogger<BackendApi> _logger;
    private string? _token;   // JWT от FastAPI

    public BackendApi(IHttpClientFactory f, ILogger<BackendApi> logger)
    {
        _http = f.CreateClient("Backend");
        _logger = logger;
    }

    // ========== AUTH (FastAPI /login) ==========

    public async Task<bool> LoginAsync(string username, string password, CancellationToken ct = default)
    {
        var payload = new { username, password };

        var resp = await _http.PostAsJsonAsync("/login", payload, ct);
        if (!resp.IsSuccessStatusCode)
        {
            _logger.LogWarning("Backend login failed: {Status}", resp.StatusCode);
            return false;
        }

        var token = await resp.Content.ReadFromJsonAsync<TokenDto>(cancellationToken: ct);
        if (token?.access_token is null)
        {
            _logger.LogWarning("Backend login: no token");
            return false;
        }

        _token = token.access_token;
        _http.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", token.access_token);

        return true;
    }

    // ========== TOPICS (/topics) ==========

    public async Task<IReadOnlyList<TopicResponseDto>> GetTopicsAsync(CancellationToken ct = default)
    {
        var topics = await _http.GetFromJsonAsync<List<TopicResponseDto>>("/topics", ct);
        return topics ?? new();
    }

    public async Task<TopicResponseDto?> GetTopicAsync(int topicId, CancellationToken ct = default)
    {
        return await _http.GetFromJsonAsync<TopicResponseDto>($"/topics/{topicId}", ct);
    }

    // ========== TESTS ==========

    public async Task<TestSessionResponseDto?> StartTestAsync(int topicId, CancellationToken ct = default)
    {
        var resp = await _http.PostAsync($"/topics/{topicId}/start-test", content: null, ct);
        if (!resp.IsSuccessStatusCode)
        {
            _logger.LogWarning("StartTest failed: {Status}", resp.StatusCode);
            return null;
        }

        return await resp.Content.ReadFromJsonAsync<TestSessionResponseDto>(cancellationToken: ct);
    }

    public async Task<IReadOnlyList<QuestionResponseDto>> GetTestQuestionsAsync(int sessionId, CancellationToken ct = default)
    {
        var questions = await _http.GetFromJsonAsync<List<QuestionResponseDto>>($"/test/{sessionId}/questions", ct);
        return questions ?? new();
    }

    public async Task<TestResultResponseDto?> SubmitTestAsync(int sessionId, TestSubmitDto submit, CancellationToken ct = default)
    {
        var resp = await _http.PostAsJsonAsync($"/test/{sessionId}/submit", submit, ct);
        if (!resp.IsSuccessStatusCode)
        {
            _logger.LogWarning("SubmitTest failed: {Status}", resp.StatusCode);
            return null;
        }

        return await resp.Content.ReadFromJsonAsync<TestResultResponseDto>(cancellationToken: ct);
    }

    // ========== CHAT ==========

    public async Task<string> ChatAsync(string model, IReadOnlyList<ChatMessage> messages, CancellationToken ct = default)
    {
        var payload = new
        {
            model,
            stream = false,
            options = new Dictionary<string, object>(),
            messages = messages
                .Select(m => new { role = m.Role.ToString().ToLowerInvariant(), content = m.Text })
                .ToList()
        };

        _logger.LogInformation("POST {Url}", new Uri(_http.BaseAddress!, "api/chat"));

        var resp = await _http.PostAsJsonAsync("api/chat", payload, ct);
        resp.EnsureSuccessStatusCode();

        var json = await resp.Content.ReadFromJsonAsync<OllamaChatResponse>(cancellationToken: ct);
        return json?.message?.content ?? "";
    }

    public async Task<bool> RegisterAsync(string email, string password, CancellationToken ct = default)
{
    var payload = new
    {
        username = email,  // используем email как username
        email = email,
        password = password
    };

    var resp = await _http.PostAsJsonAsync("/register", payload, ct);
    return resp.IsSuccessStatusCode;
}
    // ========== TEST HISTORY ==========

    public async Task<IReadOnlyList<TestSessionResponseDto>> GetTestHistoryAsync(
    ClaimsPrincipal user,
    int skip = 0,
    int limit = 20,
    CancellationToken ct = default)
{
    var ok = await EnsureBackendLoginAsync(user, ct);
    if (!ok)
        return [];

    var url = $"/test/history?skip={skip}&limit={limit}";
    var tests = await _http.GetFromJsonAsync<List<TestSessionResponseDto>>(url, ct);
    return tests ?? [];
}


    public async Task<bool> EnsureBackendLoginAsync(
    ClaimsPrincipal user,
    CancellationToken ct = default)
{
    if (_token != null)
        return true;

    var email = user.Identity?.Name;
    if (string.IsNullOrEmpty(email))
        return false;

    // ⚠️ временно: пароль = email (или фиксированный)
    // лучше сделать отдельный сервисный логин
    return await LoginAsync(email, email, ct);
}


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
