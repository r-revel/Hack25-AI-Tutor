//AiRepetitor\Services\BackendDtos.cs
using System.Text.Json.Serialization;

namespace AiRepetitor.Services;

// ---------- AUTH ----------
public sealed record TokenDto(string access_token, string token_type);

// ---------- TOPICS ----------
public sealed record TopicResponseDto(
    int id,
    string title,
    string description,
    bool is_available,
    string json
);

// ✅ ДОБАВЬ ЭТО
public sealed record TopicCreateDto(
    [property: JsonPropertyName("title")] string title,
    [property: JsonPropertyName("description")] string? description = null,
    [property: JsonPropertyName("image")] string? image = null,
    [property: JsonPropertyName("json")] string? json = null
);

// ---------- QUESTIONS / TESTS ----------
public sealed record QuestionResponseDto(
    int id,
    string question_text,
    string option_a,
    string option_b,
    string option_c,
    string option_d
);

public sealed record TestSessionResponseDto(
    int id,
    int topic_id,
    int user_id,
    DateTime started_at,
    DateTime? completed_at,
    int? total_score
);

public sealed record TestAnswerSubmitDto(int question_id, string user_answer);
public sealed record TestSubmitDto(List<TestAnswerSubmitDto> answers);

public sealed record TestResultResponseDto(
    TestSessionResponseDto session,
    int correct_answers,
    int total_questions,
    double percentage
);

// ---------- PROGRESS ----------
public sealed record UserProgressResponseDto(
    int id,
    int user_id,
    int topic_id,
    string message,
    DateTime created_at
);
