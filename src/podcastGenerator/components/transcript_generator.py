from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from typing import Dict, List
from langchain_core.runnables import RunnablePassthrough
from src.podcastGenerator import config
from docx import Document
import os
from pathlib import Path

def get_improved_prompt_template() -> PromptTemplate:
    """Create an improved prompt template for high-quality transcript generation."""
    template = """You are the host of Mental Models Daily, a podcast dedicated to explaining one mental model each day to help listeners elevate their decision making. Your task is to create a transcript for a podcast episode about {model_name}.

Follow this exact structure:

1. Opening (Standard Welcome):
"Welcome to Mental Models Daily, where we explore one mental model each day to help you elevate your daily decision making. Today, we're diving into [introduce model in an intriguing way]: {model_name}."

2. Core Concept Definition:
- Define the concept clearly and simply
- Use a primary analogy that captures the essence ("It's like...")
- Explain why this concept matters in decision making

<break time="{break_duration}" />

3. Historical Example:
- Choose one compelling historical example that clearly demonstrates the model
- Explain what happened and why it matters
- Include a relatable analogy to make the example more memorable
- Focus on specific details and outcomes

<break time="{break_duration}" />

4. Modern Business Application:
- Select a contemporary business example (preferably within last 20 years)
- Show how the mental model explains success or failure
- Include specific numbers or outcomes where possible
- Add a relatable analogy to reinforce the point

<break time="{break_duration}" />

5. Practical Applications:
Start with: "Let's explore three practical ways to [use/apply/combat] [mental model] in our daily lives:"

For each application:
- Make it specific and actionable
- Include a clear example
- Add a unique "It's like..." analogy
- Focus on practical implementation

6. Conclusion:
- Summarize the key insights about the mental model
- Emphasize its practical value in decision making
- End with a thematic sign-off related to the model

7. Standard Outro:
"For more mental models, please visit mentalmodelsdaily.com or find us on X or Instagram. Our Podcast music was provided by thePodcasthost.com & Alitu: The Podcast Maker. Find your own free podcast music over at thePodcasthost.com/freemusic."

Style Guidelines:
- Use a conversational, engaging tone throughout
- Each analogy should start with "It's like..."
- Every example should include specific details and outcomes
- Use transitions between sections to maintain flow
- Keep the total length similar to the Anchoring and Analysis Paralysis examples
- Maintain consistent voice and energy throughout

Generate a transcript that follows this structure exactly for {model_name}:"""

    return PromptTemplate(
        input_variables=["model_name", "break_duration"],
        template=template
    )

def save_transcript(transcript: str, output_path: str, model_name: str):
    """Save the transcript to a Word document."""
    doc = Document()
    doc.add_paragraph(transcript)
    
    os.makedirs(output_path, exist_ok=True)
    
    model_name_lower = model_name.lower().replace(" ", "-")
    file_path = os.path.join(output_path, f"{model_name_lower}_transcript.docx")
    doc.save(file_path)

def clean_transcript(transcript: str) -> str:
    """Clean and format the transcript to match the desired output format."""
    
    # Define standard components
    STANDARD_WELCOME = "Welcome to Mental Models Daily, where we explore one mental model each day"
    STANDARD_OUTRO = ("For more mental models, please visit mentalmodelsdaily.com or "
                     "find us on X or Instagram. Our Podcast music was provided by "
                     "thePodcasthost.com & Alitu: The Podcast Maker. Find your own free "
                     "podcast music over at thePodcasthost.com/freemusic.")
    
    # Clean up the transcript
    lines = transcript.splitlines()
    
    # Remove any empty lines at the start
    while lines and not lines[0].strip():
        lines.pop(0)
    
    # Ensure standard welcome
    if not lines[0].startswith(STANDARD_WELCOME):
        lines.insert(0, STANDARD_WELCOME)
    
    # Clean up break tags
    lines = [line.strip() for line in lines]
    lines = [line for line in lines if line]
    
    # Ensure proper break tag format
    lines = [line.replace('<break>', '<break time="1.3s" />') for line in lines]
    
    # Ensure standard outro
    if STANDARD_OUTRO not in transcript:
        lines.append(STANDARD_OUTRO)
    
    # Join lines with proper spacing
    cleaned_transcript = '\n\n'.join(lines)
    
    # Fix any common formatting issues
    cleaned_transcript = (cleaned_transcript
        .replace("\\'", "'")
        .replace('\\n', '\n')
        .replace('\\', '')
        .replace('<break time="1.3s" />', '\n<break time="1.3s" />\n'))
    
    return cleaned_transcript

def validate_transcript(transcript: str) -> bool:
    """Validate that the transcript meets all quality requirements."""
    required_elements = [
        "Welcome to Mental Models Daily",
        "It's like",
        "<break time=\"1.3s\" />",
        "Let's explore three",
        "mentalmodelsdaily.com"
    ]
    
    return all(element in transcript for element in required_elements)

def generate_transcripts(mental_models: List[str], output_path: str) -> Dict[str, str]:
    """Generate high-quality transcripts with improved structure and consistency."""
    
    llm = ChatAnthropic(
        model = config.MODEL,
        temperature = config.TEMPERATURE
    )
    
    # Create the prompt template
    prompt = get_improved_prompt_template()
    
    # Create the chain using the new syntax
    chain = (
        RunnablePassthrough() 
        | prompt 
        | llm 
        | StrOutputParser()
    )
    
    transcripts = {}
    break_duration = config.TRANSCRIPT_BREAK_DURATION
    
    for model in mental_models:
        # Invoke the chain with the input dictionary
        transcript = chain.invoke({
            "model_name": model,
            "break_duration": break_duration
        })
        
        cleaned_transcript = clean_transcript(transcript)
        
        if validate_transcript(cleaned_transcript):
            transcripts[model] = cleaned_transcript
            save_transcript(cleaned_transcript, output_path, model)
        else:
            # Retry with more explicit instructions if validation fails
            transcript = chain.invoke({
                "model_name": model,
                "break_duration": break_duration,
                "additional_context": "Please ensure all required elements are included."
            })
            cleaned_transcript = clean_transcript(transcript)
            transcripts[model] = cleaned_transcript
            save_transcript(cleaned_transcript, output_path, model)
    
    return transcripts