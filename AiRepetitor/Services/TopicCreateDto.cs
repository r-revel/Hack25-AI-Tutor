
public class TopicCreateDto
{
    public string Name { get; set; }
    public string Description { get; set; }

    // You can add a constructor if you want to initialize with default values
    public TopicCreateDto(string name = "", string description = "")
    {
        Name = name;
        Description = description;
    }
}