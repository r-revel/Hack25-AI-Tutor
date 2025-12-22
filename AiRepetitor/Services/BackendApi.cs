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

    private const string ServiceUser = "service@airepetitor.ru";
    private const string ServicePassword = "super-secret";

    public BackendApi(IHttpClientFactory f, ILogger<BackendApi> logger)
    {
        _http = f.CreateClient("Backend");
        _logger = logger;

        // сразу установить токен
        SetToken("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzZXJ2aWNlQGFpcmVwZXRpdG9yLnJ1IiwiZXhwIjoxNzY2Mzk2MTcwfQ.BD8gN8Ce_zhBB4Kt1rzxyf0k1Vq1i1ZwZYHvig8a9V8");
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

        SetToken(token.access_token);
        return true;
    }

    // Метод для ручного задания токена
    public void SetToken(string token)
    {
        _token = token;
        _http.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", token);
    }

    // ========== TOPICS (/topics) ==========

    public async Task<IReadOnlyList<TopicResponseDto>> GetTopicsAsync(CancellationToken ct = default)
    {
        await EnsureBackendLoginAsync(null, ct);
        var topics = await _http.GetFromJsonAsync<List<TopicResponseDto>>("/topics", ct);
        return topics ?? new();
    }

    public async Task<TopicResponseDto?> GetTopicAsync(int topicId, CancellationToken ct = default)
    {
        await EnsureBackendLoginAsync(null, ct);
        return await _http.GetFromJsonAsync<TopicResponseDto>($"/topics/{topicId}", ct);
    }

    // ========== TESTS ==========

    public async Task<TestSessionResponseDto?> StartTestAsync(int topicId, CancellationToken ct = default)
    {
        await EnsureBackendLoginAsync(null, ct);
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
        await EnsureBackendLoginAsync(null, ct);
        var questions = await _http.GetFromJsonAsync<List<QuestionResponseDto>>($"/test/{sessionId}/questions", ct);
        return questions ?? new();
    }

    public async Task<TestResultResponseDto?> SubmitTestAsync(int sessionId, TestSubmitDto submit, CancellationToken ct = default)
    {
        await EnsureBackendLoginAsync(null, ct);
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
        await EnsureBackendLoginAsync(null, ct);

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
            username = email,
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
            return new List<TestSessionResponseDto>();

        var url = $"/test/history?skip={skip}&limit={limit}";
        var tests = await _http.GetFromJsonAsync<List<TestSessionResponseDto>>(url, ct);
        return tests ?? new List<TestSessionResponseDto>();
    }

    // ========== ENSURE LOGIN ==========

    public async Task<bool> EnsureBackendLoginAsync(
        ClaimsPrincipal _,
        CancellationToken ct = default)
    {
        if (!string.IsNullOrEmpty(_token))
        {
            if (_http.DefaultRequestHeaders.Authorization == null)
            {
                _http.DefaultRequestHeaders.Authorization =
                    new AuthenticationHeaderValue("Bearer", _token);
            }
            return true;
        }

        _logger.LogInformation(
            "Logging in to backend as service account {User}",
            ServiceUser);

        var ok = await LoginAsync(ServiceUser, ServicePassword, ct);
        if (!ok)
        {
            _logger.LogWarning("Backend login failed, please check credentials");
            return false;
        }

        return true;
    }

    // ========== PROGRESS ==========

    public async Task<IReadOnlyList<UserProgressResponseDto>> GetTopicProgressAsync(
        int topicId,
        CancellationToken ct = default)
    {
        await EnsureBackendLoginAsync(null, ct);
        var resp = await _http.GetFromJsonAsync<List<UserProgressResponseDto>>(
            $"/topics/{topicId}/progress", ct);

        return resp ?? new List<UserProgressResponseDto>();
    }

    public async Task<UserProgressResponseDto?> SendTopicMessageAsync(
        int topicId,
        string message,
        CancellationToken ct = default)
    {
        await EnsureBackendLoginAsync(null, ct);
        var payload = new { message };

        var resp = await _http.PostAsJsonAsync(
            $"/topics/{topicId}/progress",
            payload,
            ct);

        if (!resp.IsSuccessStatusCode)
            return null;

        return await resp.Content.ReadFromJsonAsync<UserProgressResponseDto>(ct);
    }

    // ========== ADMIN TOPICS ==========

    public async Task<TopicResponseDto?> CreateTopicAsync(
        ClaimsPrincipal _,
        TopicCreateDto topicCreateDto,
        CancellationToken ct = default)
    {
        var ok = await EnsureBackendLoginAsync(null, ct);
        if (!ok)
            return null;

        var response = await _http.PostAsJsonAsync("/admin/topics", topicCreateDto, ct);

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogWarning("Failed to create topic: {Status}", response.StatusCode);
            return null;
        }

        return await response.Content.ReadFromJsonAsync<TopicResponseDto>(ct);
    }

    // ========== INTERNAL TYPES ==========

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
