# Biblioteca Digital API

API para gestionar una biblioteca digital, que permite el manejo de libros, autores, bibliotecarios, lectores y préstamos, así como la carga y almacenamiento de imágenes en Amazon S3.

## Ejecución del proyecto

### Pasos previos a la ejecución

Antes de ejecutar el código, asegúrate de cumplir con los siguientes requisitos:

1. **Base de datos**: crea una base de datos en MongoDB llamada `biblioteca_digital`.
   - Dentro de esta base de datos, crea las siguientes colecciones:
     - `Libro`
     - `Autor`
     - `Bibliotecario`
     - `Lector`
     - `Prestamo`

2. **Bucket de Amazon S3**: crea un bucket en S3 con el nombre `sistemas-distribuidos-upiiz-DAMOPK`.
   - Configura las credenciales de acceso a AWS en tu entorno para permitir que la API pueda realizar operaciones en este bucket.

### Pruebas
respuesta de creacion con exito de un autor en la api
![Descripción de la imagen](imagenes/crearautor.png)
respuesta de creacion con exito de un autor en la base de datos
![Descripción de la imagen](imagenes/crearautordb.png)

respuesta de creacion con exito de un bibliotecario en la api
![Descripción de la imagen](imagenes/crearbibliotecario.png)
respuesta de creacion con exito de un bibliotecario en la base de datos
![Descripción de la imagen](imagenes/crearbibliotecariodb.png)

respuesta de creacion con exito de un lector en la api
![Descripción de la imagen](imagenes/crearlector.png)
respuesta de creacion con exito de un lector en la base de datos
![Descripción de la imagen](imagenes/crearlectordb.png)

respuesta de creacion con exito de un libro en la api
![Descripción de la imagen](imagenes/crearlibro.png)
respuesta de creacion con exito de un libro en la base de datos
![Descripción de la imagen](imagenes/crearlibrodb.png)
respuesta de creacion con exito de un libro en AWS
![Descripción de la imagen](imagenes/crearlibroaws.png)

respuesta de creacion con exito de un prestamo en la api
![Descripción de la imagen](imagenes/crearprestamo.png)
respuesta de creacion con exito de un prestamo en la base de datos
![Descripción de la imagen](imagenes/crearprestamodb.png)
respuesta de creacion con exito de un prestamo en AWS
![Descripción de la imagen](imagenes/crearprestamoaws.png)
