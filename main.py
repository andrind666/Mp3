import os
import json
import random
import asyncio
import urllib.parse
import urllib.request
import ffmpeg
import edge_tts
from google import genai
from google.genai import types

client = genai.Client()

schema_cinemind = {
    "type": "OBJECT",
    "properties": {
        "judul": {"type": "STRING"},
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "scene_number": {"type": "INTEGER"},
                    "narasi": {"type": "STRING"},
                    "prompt_visual": {"type": "STRING"}
                },
                "required": ["scene_number", "narasi", "prompt_visual"]
            }
        }
    },
    "required": ["judul", "scenes"]
}

def load_topics(file_path="topics.txt"):
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Misteri Hilangnya Peradaban Atlantis | Misteri & Sejarah\n")
            
    topics = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "|" in line:
                    topik, niche = line.split("|", 1)
                    topics.append((topik.strip(), niche.strip()))
                else:
                    topics.append((line.strip(), "Umum"))
    return topics

def generate_storyboard(topik, niche):
    prompt = f"""
    Buatkan alur video storytelling cinematic untuk topik: '{topik}'.
    Niche: {niche}. Pecah menjadi 3-5 scene pendek. 
    Narasi bahasa Indonesia yang dramatis.
    Prompt visual bahasa Inggris, photorealistic, 16:9, ultra-detailed, tanpa teks.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema_cinemind,
            temperature=0.7
        )
    )
    return json.loads(response.text)

def download_pollinations_image(prompt_text, output_path):
    encoded_prompt = urllib.parse.quote(prompt_text)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&model=flux&nologo=true"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
            out_file.write(response.read())
        return True
    except Exception as e:
        print(f"❌ Gagal unduh gambar: {e}")
        return False

async def generate_voice(text, output_path):
    communicate = edge_tts.Communicate(text, "id-ID-ArdiNeural")
    await communicate.save(output_path)

def get_audio_duration(audio_path):
    probe = ffmpeg.probe(audio_path)
    return float(probe['format']['duration'])

def create_cinematic_scene(image_path, audio_path, output_path):
    duration = get_audio_duration(audio_path)
    fps = 25
    total_frames = int(duration * fps)
    
    motion_types = ['zoom_in', 'zoom_out', 'pan_right', 'pan_left']
    motion = random.choice(motion_types)
    
    if motion == 'zoom_in':
        z_expr = 'min(zoom+0.0015,1.3)'
        x_expr = 'iw/2-(iw/zoom/2)'
        y_expr = 'ih/2-(ih/zoom/2)'
    elif motion == 'zoom_out':
        z_expr = 'if(eq(on,1),1.3,max(1.0,zoom-0.0015))'
        x_expr = 'iw/2-(iw/zoom/2)'
        y_expr = 'ih/2-(ih/zoom/2)'
    elif motion == 'pan_right':
        z_expr = '1.2'
        x_expr = 'x+1.5'
        y_expr = 'ih/2-(ih/zoom/2)'
    else:
        z_expr = '1.2'
        x_expr = 'if(eq(on,1),iw/2,x-1.5)'
        y_expr = 'ih/2-(ih/zoom/2)'

    input_img = ffmpeg.input(image_path, loop=1, t=duration)
    input_audio = ffmpeg.input(audio_path)

    video = (
        input_img
        .filter('zoompan', z=z_expr, x=x_expr, y=y_expr, d=total_frames, s='1280x720', fps=fps)
        .filter('format', 'yuv420p')
    )

    out = ffmpeg.output(
        video, input_audio, output_path,
        vcodec='libx264', acodec='aac',
        pix_fmt='yuv420p', shortest=None
    )
    out.run(overwrite_output=True, quiet=True)

def concat_videos(scene_files, final_output):
    file_list = "concat_list.txt"
    with open(file_list, "w") as f:
        for file in scene_files:
            f.write(f"file '{os.path.abspath(file)}'\n")
            
    ffmpeg.input(file_list, format='concat', safe=0).output(
        final_output, c='copy'
    ).run(overwrite_output=True, quiet=True)
    
    if os.path.exists(file_list):
        os.remove(file_list)

async def main():
    daftar_topik = load_topics("topics.txt")
    if not daftar_topik:
        print("❌ File topics.txt kosong atau tidak valid!")
        return

    topik, niche = daftar_topik[0]
    output_dir = "output_render"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📌 Menggunakan topik dari topics.txt")
    print(f"⏳ Generating storyboard untuk topik: {topik} ({niche})...")
    
    story = generate_storyboard(topik, niche)
    print(f"🎬 Judul: {story['judul']}\n")
    
    scene_videos = []

    for scene in story['scenes']:
        num = scene['scene_number']
        narasi = scene['narasi']
        prompt_img = scene['prompt_visual']
        
        print(f"--- Processing Scene {num} ---")
        img_path = os.path.join(output_dir, f"scene_{num}.jpg")
        audio_path = os.path.join(output_dir, f"scene_{num}.mp3")
        video_path = os.path.join(output_dir, f"scene_{num}.mp4")
        
        await generate_voice(narasi, audio_path)
        download_pollinations_image(prompt_img, img_path)
        
        print(f"🎥 Rendering efek kamera sinematik...")
        create_cinematic_scene(img_path, audio_path, video_path)
        scene_videos.append(video_path)
        print(f"✅ Scene {num} selesai.\n")
        
    final_video = os.path.join(output_dir, "final_storytelling.mp4")
    print("📦 Menggabungkan seluruh scene...")
    concat_videos(scene_videos, final_video)
    print(f"\n🎉 SELESAI! Video tersimpan di: {final_video}")

if __name__ == "__main__":
    asyncio.run(main())
