from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
import google.generativeai as genai
import io
import os
from pathlib import Path
import mimetypes
from pydub import AudioSegment
import logging
import json
from datetime import datetime

# --- Logging Configuration ---
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(title="AcompanhAR API Gateway", version="3.0.0")

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class VitalSigns(BaseModel):
    bp_systolic: Optional[int] = Field(None, description="Pressão arterial sistólica")
    bp_diastolic: Optional[int] = Field(None, description="Pressão arterial diastólica")
    hr: Optional[int] = Field(None, description="Frequência cardíaca")
    temp_c: Optional[float] = Field(None, description="Temperatura em Celsius")
    spo2: Optional[int] = Field(None, description="Saturação de oxigênio")

class MedicationAdministered(BaseModel):
    name: Optional[str] = Field(None, description="Nome do medicamento")
    dose: Optional[str] = Field(None, description="Dose administrada")
    route: Optional[str] = Field(None, description="Via de administração")
    time: Optional[str] = Field(None, description="Horário da administração")

class HomecareReport(BaseModel):
    patient_state: Optional[str] = Field(None, description="Estado geral do paciente")
    vitals: Optional[VitalSigns] = Field(None, description="Sinais vitais")
    medications_in_use: List[str] = Field([], description="Medicamentos em uso")
    medications_administered: List[MedicationAdministered] = Field([], description="Medicamentos administrados")
    materials_used: List[str] = Field([], description="Materiais utilizados")
    interventions: List[str] = Field([], description="Intervenções realizadas")
    recommendations: List[str] = Field([], description="Recomendações")
    observations: Optional[str] = Field(None, description="Observações gerais")
    data_processamento: Optional[str] = Field(None, description="Data de processamento")

class RespostaExtracao(BaseModel):
    dados: Optional[HomecareReport] = None
    texto_bruto: Optional[str] = None
    sucesso: bool
    erro: Optional[str] = None
    caminho_arquivo_salvo: Optional[str] = None

# --- Helper Functions ---
def configure_gemini(api_key: str):
    genai.configure(api_key=api_key)

def process_audio_file(audio_file_bytes: bytes, filename: str) -> bytes:
    try:
        logger.info(f"Processing audio file: {filename}")
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_file_bytes))
        if audio_segment.channels > 1:
            audio_segment = audio_segment.set_channels(1)
        if audio_segment.frame_rate > 48000:
            audio_segment = audio_segment.set_frame_rate(48000)
        
        output_buffer = io.BytesIO()
        audio_segment.export(output_buffer, format="wav")
        logger.info(f"Successfully converted {filename} to WAV.")
        return output_buffer.getvalue()
    except Exception as e:
        logger.error(f"Could not process audio file {filename} with pydub: {e}")
        raise ValueError(f"Failed to process audio file: {e}")

def get_mime_type(filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        return mime_type
    ext = Path(filename).suffix.lower()
    mime_types_map = {
        '.m4a': 'audio/mp4', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
        '.ogg': 'audio/ogg', '.flac': 'audio/flac', '.txt': 'text/plain',
        '.py': 'text/x-python', '.json': 'application/json',
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.pdf': 'application/pdf', '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    return mime_types_map.get(ext, 'application/octet-stream')

def save_json_data(data: Dict[str, Any], identifier: str = "visit") -> str:
    save_dir = Path('results')
    save_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{timestamp}_{identifier}_homecare_report.json"
    filepath = save_dir / new_filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info(f"Homecare report saved to {filepath}")
    return str(filepath)

def create_comprehensive_prompt() -> str:
    return """
Você é um assistente especialista em análise de dados de visitas domiciliares de saúde (homecare).
Sua tarefa é analisar todos os dados fornecidos (áudios, imagens, textos) e extrair informações médicas relevantes.

Você deve retornar um JSON com a seguinte estrutura exata:

{
  "patient_state": "Estado geral do paciente (ex: estável, melhorando, necessita atenção)",
  "vitals": {
    "bp_systolic": número_inteiro_ou_null,
    "bp_diastolic": número_inteiro_ou_null,
    "hr": número_inteiro_ou_null,
    "temp_c": número_decimal_ou_null,
    "spo2": número_inteiro_ou_null
  },
  "medications_in_use": ["lista", "de", "medicamentos", "em", "uso"],
  "medications_administered": [
    {
      "name": "nome_do_medicamento",
      "dose": "dose_administrada",
      "route": "via_de_administração",
      "time": "horário_ISO_ou_null"
    }
  ],
  "materials_used": ["lista", "de", "materiais", "utilizados"],
  "interventions": ["lista", "de", "procedimentos", "realizados"],
  "recommendations": ["lista", "de", "recomendações"],
  "observations": "observações_gerais_importantes"
}

REGRAS IMPORTANTES:
1. Se uma informação não for encontrada, use null para campos únicos ou [] para listas
2. Para sinais vitais, extraia valores numéricos exatos quando mencionados
3. Para medicamentos administrados, tente extrair nome, dose, via e horário quando disponível
4. Para pressure arterial, separe em systolic e diastolic
5. Para temperature, converta para Celsius se necessário
6. Seja preciso na extração de dados médicos
7. Sua resposta deve ser APENAS o objeto JSON, sem texto adicional e sem formatação markdown

Analise todos os dados fornecidos e extraia as informações médicas relevantes:
    """

# --- API Endpoints ---
@app.get("/")
async def root():
    return {"message": "AcompanhAR API Gateway is running", "version": "3.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "AcompanhAR API Gateway"
    }

@app.post("/extract/audio-report", response_model=RespostaExtracao)
async def extract_audio_report(
    api_key: str = Form(...),
    file: UploadFile = File(...)
):
    """Legacy endpoint for single audio file processing"""
    try:
        configure_gemini(api_key)
        
        file_content = await file.read()
        mime_type = get_mime_type(file.filename)

        if not mime_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail=f"Invalid file type. Expected audio, but got {mime_type}.")

        processed_content = process_audio_file(file_content, file.filename)
        
        file_data = {
            'mime_type': 'audio/wav',
            'data': processed_content
        }

        prompt = create_comprehensive_prompt()
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content([prompt, file_data])

        try:
            cleaned_text = response.text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            extracted_data = json.loads(cleaned_text)
            report = HomecareReport(**extracted_data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode JSON from Gemini. Raw text: '{response.text}'. Error: {e}")
            return RespostaExtracao(
                sucesso=False,
                texto_bruto=response.text,
                erro="The model did not return a valid JSON object. See 'texto_bruto' for the raw response."
            )

        report.data_processamento = datetime.now().isoformat()
        saved_path = save_json_data(report.model_dump(), Path(file.filename).stem)
        
        return RespostaExtracao(
            dados=report,
            sucesso=True,
            caminho_arquivo_salvo=saved_path
        )

    except Exception as e:
        logger.error(f"Error in /extract/audio-report for file {file.filename}: {e}", exc_info=True)
        return RespostaExtracao(sucesso=False, erro=str(e))

@app.post("/extract/visit-report", response_model=RespostaExtracao)
async def extract_visit_report(
    api_key: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    texts: List[str] = Form(default=[])
):
    """New endpoint for comprehensive visit data processing"""
    try:
        configure_gemini(api_key)
        
        if not files and not texts:
            raise HTTPException(status_code=400, detail="At least one file or text must be provided.")

        logger.info(f"Processing visit report with {len(files)} files and {len(texts)} texts")
        
        # Prepare content for Gemini
        content_parts = [create_comprehensive_prompt()]
        
        # Process text inputs
        if texts:
            text_content = "\n\n--- DADOS DE TEXTO ---\n"
            for i, text in enumerate(texts, 1):
                text_content += f"Texto {i}: {text}\n"
            content_parts.append(text_content)

        # Process files
        processed_files = 0
        for file in files:
            try:
                file_content = await file.read()
                mime_type = get_mime_type(file.filename)
                
                logger.info(f"Processing file: {file.filename} (type: {mime_type})")

                if mime_type.startswith('audio/'):
                    # Process audio file
                    processed_content = process_audio_file(file_content, file.filename)
                    file_data = {
                        'mime_type': 'audio/wav',
                        'data': processed_content
                    }
                    content_parts.append(file_data)
                    processed_files += 1
                    
                elif mime_type.startswith('image/'):
                    # Process image file
                    file_data = {
                        'mime_type': mime_type,
                        'data': file_content
                    }
                    content_parts.append(file_data)
                    processed_files += 1
                    
                elif mime_type in ['application/pdf', 'text/plain']:
                    # For now, we'll save these files and note them
                    # Gemini can handle some document types directly
                    file_data = {
                        'mime_type': mime_type,
                        'data': file_content
                    }
                    content_parts.append(file_data)
                    processed_files += 1
                    
                else:
                    logger.warning(f"Unsupported file type for processing: {mime_type}")
                    continue
                    
            except Exception as file_error:
                logger.error(f"Error processing file {file.filename}: {file_error}")
                continue

        if processed_files == 0 and not texts:
            raise HTTPException(status_code=400, detail="No valid files could be processed.")

        logger.info(f"Sending {len(content_parts)} content parts to Gemini")

        # Send to Gemini
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(content_parts)

        try:
            cleaned_text = response.text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            extracted_data = json.loads(cleaned_text)
            report = HomecareReport(**extracted_data)
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to decode JSON from Gemini. Raw text: '{response.text}'. Error: {e}")
            return RespostaExtracao(
                sucesso=False,
                texto_bruto=response.text,
                erro="The model did not return a valid JSON object. See 'texto_bruto' for the raw response."
            )

        report.data_processamento = datetime.now().isoformat()
        
        # Create identifier from timestamp and number of items
        identifier = f"visit_{len(files)}files_{len(texts)}texts"
        saved_path = save_json_data(report.model_dump(), identifier)
        
        logger.info(f"Visit report processed successfully. Saved to: {saved_path}")
        
        return RespostaExtracao(
            dados=report,
            sucesso=True,
            caminho_arquivo_salvo=saved_path
        )

    except Exception as e:
        logger.error(f"Error in /extract/visit-report: {e}", exc_info=True)
        return RespostaExtracao(sucesso=False, erro=str(e))

@app.get("/reports/list")
async def list_reports():
    """List all saved reports"""
    try:
        results_dir = Path('results')
        if not results_dir.exists():
            return {"reports": []}
        
        reports = []
        for file_path in results_dir.glob("*.json"):
            try:
                stat = file_path.stat()
                reports.append({
                    "filename": file_path.name,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "size": stat.st_size
                })
            except Exception as e:
                logger.error(f"Error reading file stats for {file_path}: {e}")
                continue
        
        reports.sort(key=lambda x: x['created'], reverse=True)
        return {"reports": reports}
        
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/{filename}")
async def get_report(filename: str):
    """Get a specific report by filename"""
    try:
        file_path = Path('results') / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        return {"report": report_data, "filename": filename}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error retrieving report {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AcompanhAR API Gateway...")
    print("📖 Documentation: http://localhost:8000/docs")
    print("⚡ Health Check: http://localhost:8000/health")
    print("📊 Reports List: http://localhost:8000/reports/list")
    print("-" * 50)
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )