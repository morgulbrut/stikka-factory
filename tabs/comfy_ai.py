"""Comfy AI tab content."""

import logging
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import io
import json
import os
import time
import tomllib
from pathlib import Path
from PIL import Image
from datetime import datetime

logger = logging.getLogger("sticker_factory.tabs.comfy_ai")

# Load configuration directly from config.toml
def _load_config():
    """Load config.toml from the workspace root."""
    config_path = Path(__file__).parent.parent / "config.toml"
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except (FileNotFoundError, Exception):
        return {}

_CONFIG = _load_config()
COMFY_URL = _CONFIG.get("comfy", {}).get("url", "http://localhost:8188")
COMFY_POLL_INTERVAL = _CONFIG.get("comfy", {}).get("poll_interval", 5)

# Get Comfy AI credentials from secrets
def get_comfy_auth():
    """Get Comfy AI basic auth credentials from secrets."""
    try:
        comfy_user = st.secrets.get("comfy_user", "")
        comfy_pass = st.secrets.get("comfy_pass", "")
        if comfy_user and comfy_pass:
            return HTTPBasicAuth(comfy_user, comfy_pass)
    except Exception as e:
        logger.debug(f"No Comfy AI credentials found in secrets: {e}")
    return None


def load_workflow_template():
    """Load the Comfy AI workflow template from prompt-api.json."""
    template_path = Path(__file__).parent.parent / "comfy-ai" / "prompt-api.json"
    try:
        with open(template_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, Exception) as e:
        logger.error(f"Error loading workflow template: {e}")
        return None


def update_workflow_prompt(workflow, prompt, width, height):
    """Update the workflow with a new prompt and dimensions."""
    # Find the CLIPTextEncode node (usually node "6" based on the template)
    for node_id, node_data in workflow.get("prompt", {}).items():
        if node_data.get("class_type") == "CLIPTextEncode":
            node_data["inputs"]["text"] = prompt
            break
    
    # Find the EmptyLatentImage node (usually node "5" based on the template)
    for node_id, node_data in workflow.get("prompt", {}).items():
        if node_data.get("class_type") == "EmptyLatentImage":
            node_data["inputs"]["width"] = width
            node_data["inputs"]["height"] = height
            break
    
    return workflow


def queue_prompt(workflow):
    """Queue a prompt to Comfy AI API."""
    try:
        auth = get_comfy_auth()
        response = requests.post(
            url=f"{COMFY_URL}/prompt",
            json=workflow,
            headers={"Content-Type": "application/json"},
            auth=auth
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error queueing prompt: {e}")
        return None


def get_image(filename, subfolder="", folder_type="output"):
    """Get an image from Comfy AI API."""
    try:
        auth = get_comfy_auth()
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        response = requests.get(f"{COMFY_URL}/view", params=data, auth=auth)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    except Exception as e:
        logger.error(f"Error getting image: {e}")
        return None


def get_history(prompt_id):
    """Get the history for a prompt ID."""
    try:
        auth = get_comfy_auth()
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}", auth=auth)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return None


def render(preper_image, print_image, printer_info):
    """Render the Comfy AI tab."""
    st.subheader("Comfy AI Image Generation")
    st.write("Generate images using Comfy AI workflow")
    
    if COMFY_URL == "http://localhost:8188":
        st.info(f"Using default Comfy AI URL: {COMFY_URL}. Configure comfy.url in config.toml for custom endpoint.")
    
    # Load workflow template
    workflow_template = load_workflow_template()
    if not workflow_template:
        st.error("Could not load Comfy AI workflow template. Please check comfy-ai/prompt-api.json")
        return
    
    # Prompt input
    prompt = st.text_area("Enter a prompt", key="comfy_prompt", height=100)
    
    # Image dimensions
    col1, col2 = st.columns(2)
    with col1:
        width = st.number_input("Width", min_value=64, max_value=2048, value=624, step=64, key="comfy_width")
    with col2:
        height = st.number_input("Height", min_value=64, max_value=2048, value=464, step=64, key="comfy_height")
    
    # Initialize polling state
    if "comfy_poll_attempts" not in st.session_state:
        st.session_state.comfy_poll_attempts = 0
    if "comfy_poll_failed" not in st.session_state:
        st.session_state.comfy_poll_failed = False
    
    # Generate button
    if st.button("Generate Image", key="comfy_generate"):
        if not prompt:
            st.warning("Please enter a prompt")
        else:
            with st.spinner("Queuing prompt to Comfy AI..."):
                # Update workflow with prompt and dimensions
                workflow = update_workflow_prompt(workflow_template.copy(), prompt, width, height)
                
                # Queue the prompt
                result = queue_prompt(workflow)
                if result:
                    prompt_id = result.get("prompt_id")
                    st.session_state.comfy_prompt_id = prompt_id
                    st.session_state.comfy_generating = True
                    st.session_state.comfy_poll_attempts = 0
                    st.session_state.comfy_poll_failed = False
                    st.session_state.comfy_generated_image = None
                    st.success(f"Prompt queued! ID: {prompt_id}")
                    st.rerun()
                else:
                    st.error("Failed to queue prompt. Check Comfy AI connection.")
    
    # Poll for completed generation
    if "comfy_prompt_id" in st.session_state and st.session_state.comfy_generating:
        prompt_id = st.session_state.comfy_prompt_id
        attempts = st.session_state.comfy_poll_attempts
        max_attempts = 10
        
        if attempts < max_attempts and not st.session_state.comfy_poll_failed:
            # Check if we need to wait before polling
            current_time = time.time()
            if "comfy_last_poll_time" not in st.session_state:
                st.session_state.comfy_last_poll_time = current_time
            
            time_since_last_poll = current_time - st.session_state.comfy_last_poll_time
            
            if time_since_last_poll >= COMFY_POLL_INTERVAL or attempts == 0:
                # Poll for status
                st.session_state.comfy_poll_attempts += 1
                st.session_state.comfy_last_poll_time = current_time
                
                with st.spinner(f"Checking workflow status... (Attempt {st.session_state.comfy_poll_attempts}/{max_attempts})"):
                    history = get_history(prompt_id)
                    
                    if history and prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        image_found = False
                        
                        for node_id, node_output in outputs.items():
                            if "images" in node_output:
                                images = node_output["images"]
                                if images:
                                    # Get the first image
                                    image_info = images[0]
                                    filename = image_info["filename"]
                                    subfolder = image_info.get("subfolder", "")
                                    
                                    generated_image = get_image(filename, subfolder)
                                    if generated_image:
                                        st.session_state.comfy_generated_image = generated_image
                                        st.session_state.comfy_generating = False
                                        st.session_state.comfy_poll_attempts = 0
                                        image_found = True
                                        st.success("Image generated successfully!")
                                        break
                        
                        if not image_found:
                            # Still processing, schedule next poll
                            st.info(f"Workflow still processing... Next check in {COMFY_POLL_INTERVAL} seconds (Attempt {st.session_state.comfy_poll_attempts}/{max_attempts})")
                            # Use a short delay before rerun to avoid tight loop
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        # History not found yet, schedule next poll
                        st.info(f"Waiting for workflow to start... Next check in {COMFY_POLL_INTERVAL} seconds (Attempt {st.session_state.comfy_poll_attempts}/{max_attempts})")
                        # Use a short delay before rerun to avoid tight loop
                        time.sleep(0.5)
                        st.rerun()
            else:
                # Wait until poll interval has passed - show status and rerun quickly
                remaining_time = COMFY_POLL_INTERVAL - time_since_last_poll
                st.info(f"Waiting... Next check in {remaining_time:.1f} seconds (Attempt {attempts + 1}/{max_attempts})")
                # Use a short delay before rerun to avoid tight loop
                time.sleep(0.5)
                st.rerun()
        elif attempts >= max_attempts:
            # Max attempts reached, show error
            if not st.session_state.comfy_poll_failed:
                st.session_state.comfy_poll_failed = True
                st.session_state.comfy_generating = False
                total_time = max_attempts * COMFY_POLL_INTERVAL
                st.error(f"❌ Workflow did not complete after {max_attempts} attempts ({total_time} seconds). The workflow may have failed or is taking longer than expected.")
                logger.error(f"Comfy AI workflow {prompt_id} did not complete after {max_attempts} polling attempts")
    
    # Display generated image
    if "comfy_generated_image" in st.session_state and st.session_state.comfy_generated_image:
        generated_image = st.session_state.comfy_generated_image
        
        # Save image to temp directory
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(temp_dir, f"comfy_{current_date}.png")
        generated_image.save(filename)
        
        # Prepare images for printing
        grayscale_image, dithered_image = preper_image(generated_image, label_width=printer_info['label_width'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.image(grayscale_image, caption="Original Image")
        with col2:
            st.image(dithered_image, caption="Resized and Dithered Image")
        
        col3, col4 = st.columns(2)
        with col3:
            if st.button("Print Original Image", key="print_original_comfy"):
                print_image(grayscale_image, printer_info)
                st.success("Original image sent to printer!")
        with col4:
            if st.button("Print Dithered Image", key="print_dithered_comfy"):
                print_image(grayscale_image, printer_info, dither=True)
                st.success("Dithered image sent to printer!")

