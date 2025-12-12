using Microsoft.Extensions.AI;
using System.Net.Http.Json;

namespace AiRepetitor.Services;

public sealed class BackendApi
{
    private readonly HttpClient _http;
    private readonly ILogger<BackendApi> _logger;

    public BackendApi(IHttpClientFactory f, ILogger<BackendApi> logger)
    {
        _http = f.CreateClient("Backend");
        _logger = logger;
    }

    public async Task<string> ChatAsync(string model, IReadOnlyList<ChatMessage> messages, CancellationToken ct = default)
    {
        // Приводим ChatMessage (Microsoft.Extensions.AI) к формату твоего FastAPI
        var payload = new
        {
            model,
            stream = false,
            options = new Dictionary<string, object>(),
            messages = messages
                .Where(m => m.Role != ChatRole.System) // system можно оставить/убрать, как тебе нужно
                .Select(m => new { role = m.Role.ToString().ToLowerInvariant(), content = m.Text })
                .ToList()
        };

        _logger.LogInformation("POST {Url}", new Uri(_http.BaseAddress!, "api/chat"));

        var resp = await _http.PostAsJsonAsync("api/chat", payload, ct);
        resp.EnsureSuccessStatusCode();

        var json = await resp.Content.ReadFromJsonAsync<OllamaChatResponse>(cancellationToken: ct);
        return json?.message?.content ?? "";
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
