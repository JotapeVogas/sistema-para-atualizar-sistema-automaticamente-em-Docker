from contextlib import contextmanager
from typing import Iterator
import json
import shutil
from pathlib import Path

from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, status, Query, Body, Path as PathParam, UploadFile, File

from fastapi.responses import FileResponse
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session

from pydantic import BaseModel, EmailStr, Field

from typing import Optional, List, Literal

from dotenv import load_dotenv

import os

load_dotenv()

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo SQLAlchemy
class SistemaDB(Base):
    __tablename__ = "sistemas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    arquivo = Column(String, nullable=True)

# Criar tabelas
Base.metadata.create_all(bind=engine)

@contextmanager
def Database() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelos Pydantic
class SistemaBase(BaseModel):
    id: Optional[int] = Field(None, description="ID do sistema")
    nome: str = Field(description="nome do sistema")
    version: Optional[int] = Field(None, description="Versão do sistema")
    arquivo: Optional[str] = Field(None, description="Caminho do arquivo .exe do sistema")

class SistemaCreate(SistemaBase):
    pass

class SistemaResponse(SistemaBase):
    id: int
    version: int
    arquivo: Optional[str] = None

    class Config:
        from_attributes = True
        
    @classmethod
    def model_validate(cls, obj):
        if hasattr(obj, 'nome'):
            data = {
                'id': obj.id,
                'nome': obj.nome,
                'version': obj.version,
                'arquivo': obj.arquivo
            }
            return cls(**data)
        return super().model_validate(obj)

# Rotas
@app.get("/", response_model=dict, 
        summary="Página inicial",
        description="Redireciona para a documentação interativa da API (Swagger UI).") 
def home():
    return {"escreva na URL": "http://127.0.0.1:5000/docs#/"}

@app.get("/sistemas/", response_model=List[SistemaResponse],
         summary="Listar sistemas",
         description="Lista todos os sistemas cadastrados")
def listar_sistemas(sistema_nome: Optional[str] = Query(None, description="Nome do sistema para filtrar")):
    try:
        with Database() as db:
            if sistema_nome:
                sistemas = db.query(SistemaDB).filter(SistemaDB.nome == sistema_nome).all()
                return [SistemaResponse.model_validate(sistema) for sistema in sistemas]
            else:
                sistemas = db.query(SistemaDB).all()
                return [SistemaResponse.model_validate(sistema) for sistema in sistemas]
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar sistemas: {str(e)}"
        )


@app.get('/sistemas/{id_sistema}/download',
         summary='Download do arquivo do sistema',
         description='Faz o download do arquivo .exe do sistema pelo ID')
def download_arquivo_sistema(id_sistema: int):
    try:
        with Database() as db:
            sistema = db.query(SistemaDB).filter(SistemaDB.id == id_sistema).first()
            if not sistema or not sistema.arquivo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sistema com ID {id_sistema} não encontrado ou sem arquivo"
                )

            if sistema.arquivo and Path(sistema.arquivo).exists():
                return FileResponse(
                    path=sistema.arquivo, 
                    media_type='application/x-msdownload',
                    filename=sistema.nome + '.exe'
                )
            arquivo_path = Path( Path(__file__).resolve().parent / Path('static') / 'sistemas' / sistema.nome / str(sistema.version) / f'{sistema.nome}.exe' )
            # if not arquivo_path.exists():
            #     raise HTTPException(
            #         status_code=status.HTTP_404_NOT_FOUND,
            #         detail="Arquivo não encontrado no servidor"
            #     )

            return FileResponse(
                path=str(arquivo_path), 
                media_type='application/x-msdownload',
                filename=sistema.nome + '.exe'
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao fazer download do arquivo: {str(e)}"
        )
    

# @app.get("/sistemas", response_model=SistemaResponse,
#          summary="Listar sistema por nome",
#          description="Lista um sistema cadastrado pelo seu nome")
# def listar_sistema_por_nome(sistema_nome: str = Query(...)):
#     try:
#         with Database() as db:
#             sistema = db.query(SistemaDB).filter(SistemaDB.nome == sistema_nome).first()
#             if not sistema:
#                 raise HTTPException(
#                     status_code=status.HTTP_404_NOT_FOUND,
#                     detail=f"Sistema com nome {sistema_nome} não encontrado"
#                 )
#             return SistemaResponse.model_validate(sistema)

#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Erro ao listar sistema: {str(e)}"
#         )
#     except HTTPException:
#         raise

@app.get("/sistemas/{sistema_id}", response_model=SistemaResponse,
         summary="Listar sistema por ID",
         description="Lista um sistema cadastrado pelo seu ID")
def listar_sistema_por_id(sistema_id: int):
    try:
        with Database() as db:
            sistema = db.query(SistemaDB).filter(SistemaDB.id == sistema_id).first()
            if not sistema:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sistema com ID {sistema_id} não encontrado"
                )
            return SistemaResponse.model_validate(sistema)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar sistema: {str(e)}"
        )
    except HTTPException:
        raise

@app.post("/sistema/", response_model=SistemaResponse,
          summary="Criar novo sistema",
          description="Cria um novo sistema no banco de dados")
def criar_sistema(sistema: SistemaCreate):
    try:
        with Database() as db:
            # Criar novo sistema
            novo_sistema = SistemaDB(
                nome=sistema.nome,  # Usando 'nome' na tabela
                version=1  # Versão inicial sempre 1
            )
            
            db.add(novo_sistema)
            db.commit()
            db.refresh(novo_sistema)
            
            return SistemaResponse.model_validate(novo_sistema)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar sistema: {str(e)}"
        )

@app.patch('/sistema/', summary='Atualizar sistema',
           description='Atualiza o registro do sistema existente')
def atualizar_cadastro_sistema(sistema_info: SistemaCreate = Body(...)):
    try:
        with Database() as db:
            db_sistema = db.query(SistemaDB).filter(SistemaDB.id == sistema_info.id).update(
                sistema_info.model_dump(exclude_unset=True, exclude={'id'})
            )
            if not db_sistema:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sistema com ID {sistema_info.id} não encontrado"
                )
            db.commit()
            return JSONResponse({'mensagem':'Sucesso!'},200)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar sistema: {str(e)}"
        )
    except HTTPException:
        raise

@app.post("/sistema/{sistema_id}/arquivo",
          summary="Adicionar arquivo ao sistema",
          description="Adiciona arquivo .exe ao sistema e incrementa a versão")
async def adicionar_arquivo_sistema(
    sistema_id: int = PathParam(..., description="ID do sistema"),
    arquivo: UploadFile = File(..., description="Arquivo .exe do sistema")
):

    try:
        # Verificar se o arquivo é um .exe
        if not arquivo.content_type == 'application/x-msdownload':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O arquivo deve ser um executável (.exe)"
            )
        # if not arquivo.filename.lower().endswith('.exe'):
        #     raise HTTPException(
        #         status_code=status.HTTP_400_BAD_REQUEST,
        #         detail="O arquivo deve ser um executável (.exe)"
        #     )
        
        with Database() as db:
            # Buscar o sistema no banco
            sistema = db.query(SistemaDB).filter(SistemaDB.id == sistema_id).first()
            if not sistema:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sistema com ID {sistema_id} não encontrado"
                )
            
            # nova_versao = sistema.version + 1
            
            base_dir = Path(f"static/sistemas/{sistema.nome}/{sistema.version}")
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # versoes_existentes = []
            # for pasta in base_dir.iterdir():
            #     if pasta.is_dir() and pasta.name.isdigit():
            #         versoes_existentes.append(int(pasta.name))
            
            # versao_maxima_pasta = max(versoes_existentes) if versoes_existentes else 0
            
            # if versao_maxima_pasta >= nova_versao:
            #     nova_versao = versao_maxima_pasta + 1
            
            # versao_dir = base_dir / str(nova_versao)
            # versao_dir.mkdir(exist_ok=True)
            
            # arquivo_destino = versao_dir / "main.exe"


            
            with open(base_dir / arquivo.filename, "wb") as arq:
                arq.write(arquivo.file.read())
                # shutil.copyfileobj(arquivo.file, buffer)
            
            # sistema.version = nova_versao
            # sistema.arquivo = str(arquivo_destino)  # Usar 'arquivo'
            # db.commit()
            # db.refresh(sistema)
            
            return JSONResponse({'mensagem':'Sucesso!'},201)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao adicionar arquivo ao sistema: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="localhost",
        port=5000,
        reload=True,
        workers=1
    )
