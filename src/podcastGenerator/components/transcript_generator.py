from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from typing import Dict, List
from langchain_core.runnables import RunnablePassthrough
from src.podcastGenerator import config
from docx import Document
import os
from pathlib import Path
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from time import time

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_improved_prompt_template() -> PromptTemplate:
    """Create an improved prompt template for high-quality transcript generation."""
    template = """You are the host of Mental Models Daily, a podcast dedicated to explaining one mental model each day to help listeners elevate their decision making. Your task is to create a transcript for a podcast episode about {model_name}. Ensure that sections 2-5 are clearly separated by '<break time="{break_duration}" />'. These tags must be included verbatim in the output, with the exact format and placement as described.

Follow this exact structure:

1. Opening (Standard Welcome):
"Welcome to Mental Models Daily, where we explore one mental model each day to help you elevate your daily decision making. Today, we're diving into [introduce model in an intriguing way]: {model_name}."

<break time="1s" />  <!-- Hardcode 1s for the first break -->

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
Start with: "Let's explore three ways to thoughtfully [use/apply/combat] {model_name} in our daily lives:"

For each application:
- Clearly state the application, starting with *"First,"*, *"Second,"*, and *"Third,"* to maintain structure and flow.
- Provide a brief explanation of the application and its importance.
- Use a relatable and vivid analogy starting with *"It's like..."* to help the listener visualize the concept.
- Focus on actionable, realistic advice that the listener can implement.
- Ensure each application is distinct and covers diverse aspects of daily life.

<break time="{break_duration}" />

6. Conclusion:
- Summarize the key takeaways of {model_name} with a focus on its practical value.
- Acknowledge when and how to use it effectively, along with its limitations.
- End with an inspirational thematic line linked to the mental model, such as:
  "The key is to use this model selectively and intentionally, recognizing its power lies in [specific insight]."

7. Standard Outro:
End every episode with:
"Thank you for joining me today on Mental Models Daily. Until next time, may your [inspirational phrase tailored to the model]."

Always include:
"For more mental models, please visit mentalmodelsdaily.com or find us on X or Instagram. Our Podcast music was provided by thePodcasthost.com & Alitu: The Podcast Maker. Find your own free podcast music over at thePodcasthost.com/freemusic."

Style Guidelines:
- Use a conversational, engaging tone throughout
- Each analogy should start with "It's like..."
- Every example should include specific details and outcomes
- Use transitions between sections to maintain flow
- Keep the total length similar to approximately 750 to 900 words
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
    
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = output_dir / f"{model_name.lower().replace(' ', '-')}_transcript.docx"
    doc.save(file_path)
    logging.info(f"Transcript saved to: {file_path}")


def clean_transcript(transcript: str) -> str:
    """Clean and format the transcript to match the desired output format."""
    STANDARD_WELCOME = "Welcome to Mental Models Daily, where we explore one mental model each day"
    STANDARD_OUTRO = ("For more mental models, please visit mentalmodelsdaily.com or "
                      "find us on X or Instagram. Our Podcast music was provided by "
                      "thePodcasthost.com & Alitu: The Podcast Maker. Find your own free "
                      "podcast music over at thePodcasthost.com/freemusic.")

    lines = transcript.splitlines()

    # Remove empty lines at the start
    lines = [line for line in lines if line.strip()]
    
    # Ensure standard welcome and outro
    if not lines[0].startswith(STANDARD_WELCOME):
        lines.insert(0, STANDARD_WELCOME)
    if STANDARD_OUTRO not in transcript:
        lines.append(STANDARD_OUTRO)

    # Ensure proper <break> tags are included and normalized
    if "<break" not in transcript:
        logging.warning("No <break> tags found; adding default break durations.")
    transcript = re.sub(r'\\?<break\s*(?:time="(.*?)")?\\?\s*/?>', '<break time="1.3s" />', transcript)

    # Now post-process to ensure the first <break> tag after section 1 is 1s
    # Replace the first <break> tag with time="1s"
    transcript = re.sub(r'(<break\s+time=")[^"]*(" />)', r'\g<1>1s\g<2>', transcript, count=1)

    # Clean up escaping issues
    cleaned_transcript = transcript.replace("\\'", "'").replace("\\n", "\n").replace("\\", "")

    return cleaned_transcript


def validate_transcript(transcript: str) -> bool:
    """Validate the transcript against required elements."""
    required_elements = [
        "Welcome to Mental Models Daily",
        "It's like",
        "<break time=\"1.3s\" />",
        "Let's explore three",
        "mentalmodelsdaily.com"
    ]
    missing_elements = [elem for elem in required_elements if elem not in transcript]
    if missing_elements:
        logging.warning(f"Validation failed. Missing elements: {missing_elements}")
    return not missing_elements


def generate_transcripts(mental_models: List[str], output_path: str) -> Dict[str, str]:
    """Generate high-quality transcripts with improved structure and consistency."""
    llm = ChatAnthropic(
        model=config.MODEL,
        temperature=config.TEMPERATURE
    )

    prompt = get_improved_prompt_template()
    chain = RunnablePassthrough() | prompt | llm | StrOutputParser()

    transcripts = {}
    break_duration = config.TRANSCRIPT_BREAK_DURATION

    def process_model(model_name: str):
        start_time = time()
        transcript = chain.invoke({
                        "model_name": model_name,
                        "break_duration": break_duration,
                        "additional_context": "Ensure that all sections include '<break time=\"1.3s\" />' tags between sections."
                    })
        logging.debug(f"Raw transcript for {model_name}: {transcript}")
        cleaned_transcript = clean_transcript(transcript)

        if validate_transcript(cleaned_transcript):
            transcripts[model_name] = cleaned_transcript
            save_transcript(cleaned_transcript, output_path, model_name)
        else:
            logging.warning(f"Validation failed for {model_name}. Retrying with additional context.")
            transcript = chain.invoke({
                "model_name": model_name,
                "break_duration": break_duration,
                "additional_context": "Please ensure all required elements are included."
            })
            logging.debug(f"Raw transcript for {model_name}: {transcript}")
            cleaned_transcript = clean_transcript(transcript)
            transcripts[model_name] = cleaned_transcript
            save_transcript(cleaned_transcript, output_path, model_name)

        logging.info(f"Processed '{model_name}' in {time() - start_time:.2f} seconds.")

    with ThreadPoolExecutor() as executor:
        executor.map(process_model, mental_models)

    return transcripts
