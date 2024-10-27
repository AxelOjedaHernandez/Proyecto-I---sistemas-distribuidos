from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from pathlib import Path
import shutil
from pydantic import BaseModel
from motor import motor_asyncio
import boto3
from botocore.exceptions import NoCredentialsError
from datetime import datetime, timedelta
import uuid
from typing import Optional


# Configurar la conexión con MongoDB
MONGO_URI = "mongodb://localhost:27017"
cliente = motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = cliente["biblioteca_digital"]

# Configurar cliente de S3
s3 = boto3.client('s3')
BUCKET_NAME = "sistemas-distribuidos-upiiz-agoh"  # Cambia esto por tu bucket de S3


# Colecciones
prestamos_collection = db["Prestamo"]
libros_collection = db["Libro"]
lectores_collection = db["Lector"]
bibliotecarios_collection = db["Bibliotecario"]
autores_collection = db["Autor"]

# Objeto para interactuar con la API
app = FastAPI()

# Ruta de la carpeta donde se almacenarán las imágenes
IMAGES_DIR = Path("img")
IMAGES_DIR.mkdir(exist_ok=True)  # Crea la carpeta si no existe

# Modelos de datos
class Prestamo(BaseModel):
    id: int
    lector_id: int
    libro_id: int
    fecha_prestamo: datetime
    fecha_devolucion: datetime
    bibliotecario_id: int
    foto_credencial: str

class Libro(BaseModel):
    id: int
    titulo: str
    autor_id: int
    descripcion: str
    imagen_portada: str
    inventario: bool

class Lector(BaseModel):
    id: int
    nombre: str
    apellido: str
    correo: str

class Bibliotecario(BaseModel):
    id: int
    nombre: str
    apellido: str
    correo: str

class Autor(BaseModel):
    id: int
    nombre: str
    apellido: str
    biografia: str

# ---------------------------------- Prestamos -----------------------------------

@app.get("/prestamos/")
async def get_prestamos():
    resultados = dict()
    #Obtener de manera asíncrona todos los usuarios
    prestamos = await prestamos_collection.find().to_list(None)
    #Iterar todos los elementos de la lista users
    for i, prestamo in enumerate(prestamos):
        #Diccionario para cada usuario
        resultados[i] = dict()
        resultados[i]["id"]=prestamo["id"]
        resultados[i]["lector_id"]=prestamo["lector_id"]
        resultados[i]["libro_id"]=prestamo["libro_id"]
        resultados[i]["fecha_prestamo"]=prestamo["fecha_prestamo"]
        resultados[i]["fecha_devolucion"]=prestamo["fecha_devolucion"]
        resultados[i]["bibliotecario_id"]=prestamo["bibliotecario_id"]
        resultados[i]["foto_credencial"]=prestamo["foto_credencial"]
    return resultados

@app.get("/prestamo/{id}")
async def get_prestamo(id: int):
    
    # Convertir el id a ObjectId y buscar el usuario en la colección
    resultado = await prestamos_collection.find_one({"id": id})
    
    if resultado:
        return {
            "id": resultado["id"],
            "lector_id": resultado["lector_id"],
            "libro_id": resultado["libro_id"],
            "fecha_prestamo": resultado["fecha_prestamo"],
            "fecha_devolucion": resultado["fecha_devolucion"],
            "bibliotecario_id": resultado["bibliotecario_id"],
            "foto_credencial": resultado["foto_credencial"]
        }
    raise HTTPException(status_code=404, detail="El prestamo no se encontró")


@app.post("/prestamo/", response_model=Prestamo)
async def create_prestamo(file: UploadFile = File(...), lector_id: int = 0, libro_id: int = 0, bibliotecario_id: int = 0):
    # Verificar si el lector_id existe
    lector = await lectores_collection.find_one({"id": lector_id})
    if not lector:
        raise HTTPException(status_code=404, detail="El lector no existe")

    # Verificar si el libro_id existe
    libro = await libros_collection.find_one({"id": libro_id})
    if not libro:
        raise HTTPException(status_code=404, detail="El libro no existe")
     # Verificar disponibilidad de inventario del libro
    if not libro["inventario"]:
        raise HTTPException(status_code=400, detail="El libro no está disponible en inventario")

    # Verificar si el bibliotecario_id existe
    bibliotecario = await bibliotecarios_collection.find_one({"id": bibliotecario_id})
    if not bibliotecario:
        raise HTTPException(status_code=404, detail="El bibliotecario no existe")

    # Buscar el préstamo con el id más alto y sumarle 1
    ultimo_prestamo = await prestamos_collection.find_one(sort=[("id", -1)])
    if ultimo_prestamo:
        nuevo_id = ultimo_prestamo["id"] + 1
    else:
        nuevo_id = 1  # Si no hay préstamos, se comienza desde 1

    # Crear el nombre de archivo para la foto y subirla a s3
    imagen_url = upload_image_to_s3(file, BUCKET_NAME,"credenciales")
    
    # Crear un nuevo préstamo con el id incrementado
    nuevo_prestamo = dict()
    nuevo_prestamo["id"] = nuevo_id
    nuevo_prestamo["lector_id"] = lector_id
    nuevo_prestamo["libro_id"] = libro_id
    # Establecer la fecha actual para fecha_prestamo y tres días después para fecha_devolucion
    nuevo_prestamo["fecha_prestamo"] = datetime.now()  # Fecha actual
    nuevo_prestamo["fecha_devolucion"] = datetime.now() + timedelta(days=3)  # Tres días después
    nuevo_prestamo["bibliotecario_id"] = bibliotecario_id
    nuevo_prestamo["foto_credencial"] = str(imagen_url)  # Almacenar la ruta de la imagen

    #print(nuevo_prestamo)
    # Insertar el nuevo préstamo en la colección
    await prestamos_collection.insert_one(nuevo_prestamo)
    # Actualizar el inventario del libro a False
    await libros_collection.update_one(
        {"id": libro_id},
        {"$set": {"inventario": False}}
    )
    # Devolver el nuevo préstamo con las fechas en formato ISO 8601
    prestamo_dict = {
        "id": nuevo_prestamo["id"],  # Asegúrate de que se devuelve el nuevo id
        "lector_id": nuevo_prestamo["lector_id"],
        "libro_id": nuevo_prestamo["libro_id"],
        "fecha_prestamo": nuevo_prestamo["fecha_prestamo"].isoformat(),  # Formato ISO 8601
        "fecha_devolucion": nuevo_prestamo["fecha_devolucion"].isoformat(),  # Formato ISO 8601
        "bibliotecario_id": nuevo_prestamo["bibliotecario_id"],
        "foto_credencial": nuevo_prestamo["foto_credencial"]
    }

    return prestamo_dict

@app.put("/prestamo/{id}", response_model=Prestamo)
async def update_prestamo(
    id: int,
    lector_id: Optional[int] = Form(None),
    libro_id: Optional[int] = Form(None),
    fecha_prestamo: Optional[datetime] = Form(None),
    bibliotecario_id: Optional[int] = Form(None),
    foto_credencial: Optional[UploadFile] = File(None)
    ):
    update_data = {}
    if lector_id is not None:
        update_data["lector_id"] = lector_id
    if libro_id is not None:
        update_data["libro_id"] = libro_id
    if fecha_prestamo is not None:
        update_data["fecha_prestamo"] = fecha_prestamo
        update_data["fecha_devolucion"] = fecha_prestamo + timedelta(days=3)
    if bibliotecario_id is not None:
        update_data["bibliotecario_id"] = bibliotecario_id

    if not update_data and foto_credencial is None:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    
    # Verificar si el lector_id existe
    if "lector_id" in update_data:
        lector = await lectores_collection.find_one({"id": lector_id})
        if not lector:
            raise HTTPException(status_code=404, detail="El lector no existe")

    # Verificar si el libro_id existe
    if "libro_id" in update_data:
        libro = await libros_collection.find_one({"id": libro_id})
        if not libro:
            raise HTTPException(status_code=404, detail="El libro no existe")

    # Verificar si el bibliotecario_id existe
    if "bibliotecario_id" in update_data:
        bibliotecario = await bibliotecarios_collection.find_one({"id": bibliotecario_id})
        if not bibliotecario:
            raise HTTPException(status_code=404, detail="El bibliotecario no existe")

    if foto_credencial:
        imagen_url = upload_image_to_s3(foto_credencial, BUCKET_NAME, "credenciales")

        update_data["foto_credencial"] = imagen_url  # Actualizar el campo imagen_portada con la nueva URL

   
     # Actualizar el prestamo en la base de datos
    result = await prestamos_collection.update_one(
        {"id": id},
        {"$set": update_data}
    )

    # Verificar si se realizó alguna actualización
    if result.matched_count == 1:
        # Si el préstamo fue actualizado correctamente, devolver la nueva información
        updated_prestamo = await prestamos_collection.find_one({"id": id})
        if updated_prestamo:
            return updated_prestamo

    # Si no se encuentra el préstamo, lanzar un error 404
    raise HTTPException(status_code=404, detail="El préstamo no se encontró")

@app.delete("/prestamo/{id}")
async def delete_prestamo(id: int):
    # Buscar el préstamo por su ID para obtener el libro_id asociado
    prestamo = await prestamos_collection.find_one({"id": id})
    
    if not prestamo:
        raise HTTPException(status_code=404, detail="El préstamo no se encontró")

    # Eliminar el préstamo
    result = await prestamos_collection.delete_one({"id": id})
    
    if result.deleted_count == 1:
        # Actualizar el inventario del libro a True
        await libros_collection.update_one(
            {"id": prestamo["libro_id"]},
            {"$set": {"inventario": True}}
        )
        
        return {
            "message": "El préstamo se eliminó correctamente"
        }
    
    raise HTTPException(status_code=404, detail="Error al eliminar el préstamo")

# ------------------------------- Libro -------------------------------

@app.get("/libros/")
async def get_libros():
    resultados = dict()
    #Obtener de manera asíncrona todos los usuarios
    libros = await libros_collection.find().to_list(None)
    #Iterar todos los elementos de la lista users
    for i, libro in enumerate(libros):
        #Diccionario para cada usuario
        resultados[i] = dict()
        resultados[i]["id"]=libro["id"]
        resultados[i]["titulo"]=libro["titulo"]
        resultados[i]["autor_id"]=libro["autor_id"]
        resultados[i]["descripcion"]=libro["descripcion"]
        resultados[i]["imagen_portada"]=libro["imagen_portada"]
        resultados[i]["inventario"]=libro["inventario"]
    return resultados

@app.get("/libro/{id}")
async def get_libro(id: int):
    
    # Convertir el id a ObjectId y buscar el usuario en la colección
    resultado = await libros_collection.find_one({"id": id})
    
    if resultado:
        return {
            "id": resultado["id"],
            "autor_id": resultado["autor_id"],
            "descripcion": resultado["descripcion"],
            "imagen_portada": resultado["imagen_portada"],
            "inventario": resultado["inventario"]
        }
    raise HTTPException(status_code=404, detail="El libro no se encontró")

# Ruta para crear un nuevo libro con imagen (Create)
@app.post("/libro", response_model=Libro)
async def create_libro(file: UploadFile = File(...), titulo: str = "", autor_id: int = 0, descripcion: str = "", inventario: bool = True):
    # Validar si el ID del libro ya existe
    # Buscar el préstamo con el id más alto y sumarle 1
    ultimo_libro = await libros_collection.find_one(sort=[("id", -1)])
    if ultimo_libro:
        nuevo_id = ultimo_libro["id"] + 1
    else:
        nuevo_id = 1  # Si no hay préstamos, se comienza desde 1

    # Verificar si el lector_id existe
    autor = await autores_collection.find_one({"id": autor_id})
    if not autor:
        raise HTTPException(status_code=404, detail="El autor no existe")
    
    # Subir imagen a S3 y obtener la URL
    imagen_url = upload_image_to_s3(file, BUCKET_NAME,"portadas")

    # Crear nuevo libro
    libro_data = {
        "id": nuevo_id,
        "titulo": titulo,
        "autor_id": autor_id,
        "descripcion": descripcion,
        "imagen_portada": imagen_url,  # Guardar la URL de la imagen en el libro
        "inventario": inventario
    }
    # Insertar libro en la base de datos
    libros_collection.insert_one(libro_data)
    return libro_data

# Ruta para actualizar un libro con la opción de subir una nueva imagen
@app.put("/libro/{libro_id}", response_model=Libro)
async def update_libro(
    libro_id: int,
    titulo: Optional[str] = Form(None),
    autor_id: Optional[int] = Form(None),
    descripcion: Optional[str] = Form(None),
    inventario: Optional[bool] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    update_data = {}

    if titulo is not None:
        update_data["titulo"] = titulo
    if autor_id is not None:
        update_data["autor_id"] = autor_id
    if descripcion is not None:
        update_data["descripcion"] = descripcion
    if inventario is not None:
        update_data["inventario"] = inventario

    if not update_data and file is None:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Verificar si el autor_id existe si está siendo actualizado
    if "autor_id" in update_data:
        autor = await autores_collection.find_one({"id": autor_id})
        if not autor:
            raise HTTPException(status_code=404, detail="El autor no existe")

    # Si se ha subido una imagen, subirla a S3 y obtener la URL
    if file:
        imagen_url = upload_image_to_s3(file, BUCKET_NAME, "portadas")

        update_data["imagen_portada"] = imagen_url  # Actualizar el campo imagen_portada con la nueva URL

    # Actualizar el libro en la base de datos
    result = await libros_collection.update_one(
        {"id": libro_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 1:
        # Recuperar el libro actualizado
        libro_actualizado = await libros_collection.find_one({"id": libro_id})
        if libro_actualizado:
            return libro_actualizado
        raise HTTPException(status_code=404, detail="Libro no encontrado después de actualizar")
    
    raise HTTPException(status_code=404, detail="Libro no encontrado")


# Ruta para eliminar un libro (Delete)
@app.delete("/libro/{libro_id}")
async def delete_libro(libro_id: int):
    result = await libros_collection.delete_one({"id": libro_id})
    if result.deleted_count == 1:
        return {"message": "Libro eliminado exitosamente"}
    raise HTTPException(status_code=404, detail="Libro no encontrado")

# Función para subir imagen a S3
def upload_image_to_s3(file: UploadFile, bucket: str, folder: str):
    
    try:
        # Generar un nombre único para la imagen
        image_filename = f"{folder}/{uuid.uuid4()}_{file.filename}"

        # Subir la imagen a S3
        s3.upload_fileobj(file.file, bucket, image_filename)

        # Generar URL pública de la imagen
        image_url = f"https://{bucket}.s3.amazonaws.com/{image_filename}"
        return image_url
    except NoCredentialsError:
        raise HTTPException(status_code=500, detail="Credenciales de AWS no encontradas")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imagen: {str(e)}")

# ------------------------------------- Lector -----------------------------------

# Obtener todos los lectores
@app.get("/lectores/")
async def get_lectores():
    resultados = {}
    lectores = await lectores_collection.find().to_list(None)
    for i, lector in enumerate(lectores):
        resultados[i] = {
            "id": lector["id"],
            "nombre": lector["nombre"],
            "apellido": lector["apellido"],
            "correo": lector["correo"],
        }
    return resultados

# Obtener un lector por ID
@app.get("/lector/{id}")
async def get_lector(id: int):
    resultado = await lectores_collection.find_one({"id": id})
    if resultado:
        return {
            "id": resultado["id"],
            "nombre": resultado["nombre"],
            "apellido": resultado["apellido"],
            "correo": resultado["correo"],
        }
    raise HTTPException(status_code=404, detail="El lector no se encontró")

# Crear un nuevo lector
@app.post("/lector", response_model=Lector)
async def create_lector(nombre: str, apellido: str, correo: str):
    ultimo_lector = await lectores_collection.find_one(sort=[("id", -1)])
    nuevo_id = ultimo_lector["id"] + 1 if ultimo_lector else 1

    lector_data = {
        "id": nuevo_id,
        "nombre": nombre,
        "apellido": apellido,
        "correo": correo
    }
    await lectores_collection.insert_one(lector_data)
    return lector_data

# Actualizar un lector existente
@app.put("/lector/{lector_id}", response_model=Lector)
async def update_lector(
    lector_id: int,
    nombre: Optional[str] = Form(None),
    apellido: Optional[str] = Form(None),
    correo: Optional[str] = Form(None),
):
    update_data = {}
    if nombre is not None:
        update_data["nombre"] = nombre
    if apellido is not None:
        update_data["apellido"] = apellido
    if correo is not None:
        update_data["correo"] = correo

    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    result = await lectores_collection.update_one(
        {"id": lector_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 1:
        lector_actualizado = await lectores_collection.find_one({"id": lector_id})
        if lector_actualizado:
            return lector_actualizado
        raise HTTPException(status_code=404, detail="Lector no encontrado después de actualizar")
    
    raise HTTPException(status_code=404, detail="Lector no encontrado")

# Eliminar un lector
@app.delete("/lector/{lector_id}")
async def delete_lector(lector_id: int):
    result = await lectores_collection.delete_one({"id": lector_id})
    if result.deleted_count == 1:
        return {"message": "Lector eliminado exitosamente"}
    raise HTTPException(status_code=404, detail="Lector no encontrado")

# ------------------------------- Bibliotecario -------------------------------
@app.get("/bibliotecarios/")
async def get_bibliotecarios():
    resultados = dict()
    #Obtener de manera asíncrona todos los bibliotecarios
    bibliotecarios = await bibliotecarios_collection.find().to_list(None)
    #Iterar todos los elementos de la lista users
    for i, bibliotecario in enumerate(bibliotecarios):
        #Diccionario para cada bibliotecario
        resultados[i] = dict()
        resultados[i]["id"]=bibliotecario["id"]
        resultados[i]["nombre"]=bibliotecario["nombre"]
        resultados[i]["apellido"]=bibliotecario["apellido"]
        resultados[i]["correo"]=bibliotecario["correo"]
    return resultados

@app.get("/bibliotecario/{id}")
async def get_bibliotecario(id: int):
    resultado = await bibliotecarios_collection.find_one({"id": id})
    if resultado:
        return {
            "id": resultado["id"],
            "nombre": resultado["nombre"],
            "apellido": resultado["apellido"],
            "correo": resultado["correo"]
        }
    raise HTTPException(status_code=404, detail="El bibliotecario no se encontró")

@app.post("/bibliotecario", response_model=Bibliotecario)
async def create_bibliotecario(nombre: str = "", apellido: str = "", correo: str = ""):
    # Obtener el último bibliotecario ordenado por "id" de forma descendente
    ultimo_bibliotecario = await bibliotecarios_collection.find_one(sort=[("id", -1)])

    # Si no existe ningún bibliotecario previo, asigna id=1
    nuevo_id = (ultimo_bibliotecario["id"] + 1) if ultimo_bibliotecario and "id" in ultimo_bibliotecario else 1
    print("Nuevo ID calculado:", nuevo_id)  # Para depuración

    bibliotecario_data = {
        "id": nuevo_id,
        "nombre": nombre,
        "apellido": apellido,
        "correo": correo
    }

    # Insertar el nuevo bibliotecario
    await bibliotecarios_collection.insert_one(bibliotecario_data)
    return bibliotecario_data


# Ruta para actualizar un bibliotecario
@app.put("/bibliotecario/{bibliotecario_id}", response_model=Bibliotecario)
async def update_bibliotecario(
    bibliotecario_id: int,
    nombre: Optional[str] = Form(None),
    apellido: Optional[str] = Form(None),
    correo: Optional[str] = Form(None)
):
    update_data = {k: v for k, v in {
        "nombre": nombre,
        "apellido": apellido,
        "correo": correo
    }.items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    result = await bibliotecarios_collection.update_one({"id": bibliotecario_id}, {"$set": update_data})
    if result.matched_count:
        return await bibliotecarios_collection.find_one({"id": bibliotecario_id})
    
    raise HTTPException(status_code=404, detail="Bibliotecario no encontrado")

# Ruta para eliminar un bibliotecario
@app.delete("/bibliotecario/{bibliotecario_id}")
async def delete_bibliotecario(bibliotecario_id: int):
    result = await bibliotecarios_collection.delete_one({"id": bibliotecario_id})
    if result.deleted_count:
        return {"message": "Bibliotecario eliminado exitosamente"}
    raise HTTPException(status_code=404, detail="Bibliotecario no encontrado")

# ---------------------------- Autor ---------------------------

@app.get("/autores/")
async def get_autores():
    resultados = dict()
    #Obtener de manera asíncrona todos los usuarios
    autores = await autores_collection.find().to_list(None)
    #Iterar todos los elementos de la lista 
    for i, autor in enumerate(autores):
        #Diccionario para cada usuario
        resultados[i] = dict()
        resultados[i]["id"]=autor["id"]
        resultados[i]["nombre"]=autor["nombre"]
        resultados[i]["apellido"]=autor["apellido"]
        resultados[i]["biografia"]=autor["biografia"]
    return resultados

@app.get("/autor/{id}")
async def get_autor(id: int):
    
    # Convertir el id a ObjectId y buscar el usuario en la colección
    resultado = await autores_collection.find_one({"id": id})
    
    if resultado:
        return {
            "id": resultado["id"],
            "nombre": resultado["nombre"],
            "apellido": resultado["apellido"],
            "biografia": resultado["biografia"]
        }
    raise HTTPException(status_code=404, detail="El autor no se encontró")

@app.post("/autor/")
async def create_autor(autor: Autor):
   
    # Buscar el préstamo con el id más alto y sumarle 1
    ultimo_autor = await autores_collection.find_one(sort=[("id", -1)])
    if ultimo_autor:
        nuevo_id = ultimo_autor["id"] + 1
    else:
        nuevo_id = 1  # Si no hay préstamos, se comienza desde 1

    # Crear un nuevo préstamo con el id incrementado
    nuevo_autor = autor.dict()
    nuevo_autor["id"] = nuevo_id

    #print(nuevo_prestamo)
    # Insertar el nuevo préstamo en la colección
    await autores_collection.insert_one(nuevo_autor)
    
    # Devolver el nuevo préstamo con las fechas en formato ISO 8601
    autor_dict = {
        "id": autor.id,
        "lector_id": autor.nombre,
        "libro_id": autor.apellido,
        "fecha_prestamo": autor.biografia
    }
    return autor_dict

@app.put("/autor/{id}")
async def update_autor(id: int, autor: Autor):
    
    # Convertir el objeto prestamo a dict y eliminar el campo "id"
    autor_data = autor.dict(exclude_unset=True)  # Excluir campos no enviados
    if "id" in autor_data:
        del autor_data["id"]  # Eliminar el campo id si está presente

    # Intentar actualizar el préstamo con el nuevo contenido, excluyendo "id"
    result = await autores_collection.update_one(
        {"id": id},  # Filtro por id
        {"$set": autor_data}  # Establecer los nuevos valores del préstamo, sin "id"
    )

    # Verificar si se realizó alguna actualización
    if result.matched_count == 1:
        # Si el préstamo fue actualizado correctamente, devolver la nueva información
        updated_autor = await autores_collection.find_one({"id": id})
        if updated_autor:
            return {
                "id": updated_autor.get("id"),
                "nombre": updated_autor.get("nombre"),
                "apellido": updated_autor.get("apellido"),
                "biografia": updated_autor.get("biografia")
            }

    # Si no se encuentra el préstamo, lanzar un error 404
    raise HTTPException(status_code=404, detail="El autor no se encontró")

@app.delete("/autor/{id}")
async def delete_autor(id: int):
    
    # Eliminar el usuario por el campo "_id"
    result = await autores_collection.delete_one({"id": id})
    
    if result.deleted_count == 1:
        return {
            "message": "El autor se eliminó correctamente"
        }
    raise HTTPException(status_code=404, detail="El autor no se encontró")


