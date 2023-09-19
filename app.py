from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.secret_key = 'clave_test'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    imagen_url = db.Column(db.String(255), nullable=True)
    precio = db.Column(db.Integer, nullable=False)


class Orden(db.Model):
    __tablename__ = 'ordenes'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)
    detalles = db.relationship('DetalleOrden', backref='orden', lazy=True)

    # Agrega un atributo para la relación con Usuario (cliente)
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])


class DetalleOrden(db.Model):
    __tablename__ = 'detalles_orden'
    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey('ordenes.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    producto = db.relationship('Producto', foreign_keys=[producto_id])


class Carrito(db.Model):
    __tablename__ = 'carrito'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)

    # Relaciones con los modelos de usuario y producto
    cliente = db.relationship('Usuario', foreign_keys=[cliente_id])
    producto = db.relationship('Producto', foreign_keys=[producto_id])


def obtener_usuario_actual():
    return current_user


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


def obtener_id_del_cliente_actual():
    return current_user.id if current_user.is_authenticated else None


def calcular_total(productos_seleccionados):
    total = Decimal('1')
    for producto_id, cantidad in productos_seleccionados.items():
        producto = Producto.query.get(producto_id)
        if producto:
            total += Decimal(str(producto.precio)) * Decimal(str(cantidad))
    total = total.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    return total


def obtener_lista_de_productos():
    return Producto.query.all()


@app.route('/')
def inicio():
    return render_template('inicio.html')


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']

        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash('El correo ya está registrado. Por favor, inicia sesión.', 'error')
            return redirect(url_for('login'))

        nuevo_usuario = Usuario(nombre=nombre, email=email, password=password)
        db.session.add(nuevo_usuario)
        db.session.commit()

        flash('¡Registro exitoso! Por favor, inicia sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('registro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.password == password:
            login_user(usuario)
            return redirect(url_for('productos'))
        else:
            flash('Credenciales incorrectas. Por favor, inténtalo de nuevo.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('inicio'))


@app.route('/productos')
@login_required
def productos():
    productos = Producto.query.all()
    return render_template('productos.html', productos=productos)


@app.route('/crear_orden', methods=['GET', 'POST'])
@login_required
def crear_orden():
    if request.method == 'POST':
        productos_seleccionados = request.form.getlist('productos_seleccionados')
        total = calcular_total(productos_seleccionados)
        nueva_orden = Orden(cliente_id=obtener_id_del_cliente_actual(), total=total)
        db.session.add(nueva_orden)
        db.session.commit()
        return redirect(url_for('detalles_orden', orden_id=nueva_orden.id))

    productos = obtener_lista_de_productos()
    return render_template('crear_orden.html', productos=productos)


@app.route('/detalles_orden/<int:orden_id>')
@login_required
def detalles_orden(orden_id):
    orden = Orden.query.get(orden_id)
    if not orden:
        return "La orden no existe."
    detalles = DetalleOrden.query.filter_by(orden_id=orden_id).all()
    return render_template('detalles_orden.html', orden=orden, detalles=detalles)


@app.route('/agregar_al_carrito/<int:producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    usuario_actual = obtener_usuario_actual()
    item_carrito_existente = Carrito.query.filter_by(cliente_id=usuario_actual.id, producto_id=producto_id).first()

    if item_carrito_existente:
        item_carrito_existente.cantidad += 1
    else:
        nuevo_item_carrito = Carrito(cliente_id=usuario_actual.id, producto_id=producto_id, cantidad=1)
        db.session.add(nuevo_item_carrito)

    db.session.commit()
    flash('Producto agregado al carrito', 'success')
    return redirect(url_for('productos'))


@app.route('/ver_carrito')
@login_required
def ver_carrito():
    usuario_actual = obtener_usuario_actual()
    items_carrito = Carrito.query.filter_by(cliente_id=usuario_actual.id).all()
    total = calcular_total({item.producto_id: item.cantidad for item in items_carrito})
    return render_template('ver_carrito.html', items_carrito=items_carrito, total=total)


@app.route('/eliminar_del_carrito/<int:producto_id>', methods=['POST'])
@login_required
def eliminar_del_carrito(producto_id):
    usuario_actual = obtener_usuario_actual()
    item_carrito_existente = Carrito.query.filter_by(cliente_id=usuario_actual.id, producto_id=producto_id).first()

    if item_carrito_existente:
        db.session.delete(item_carrito_existente)
        db.session.commit()
        flash('Producto eliminado del carrito', 'success')
    else:
        flash('El producto no está en el carrito', 'error')

    return redirect(url_for('ver_carrito'))


@app.route('/mis_ordenes')
@login_required
def mis_ordenes():
    usuario_actual = obtener_usuario_actual()
    ordenes = Orden.query.filter_by(cliente_id=usuario_actual.id).all()
    return render_template('mis_ordenes.html', ordenes=ordenes)


@app.route('/confirmar_compra', methods=['POST'])
@login_required
def confirmar_compra():
    usuario_actual = obtener_usuario_actual()
    items_carrito = Carrito.query.filter_by(cliente_id=usuario_actual.id).all()

    total = calcular_total({item.producto_id: item.cantidad for item in items_carrito})

    nueva_orden = Orden(cliente_id=usuario_actual.id, fecha=datetime.utcnow(), total=total)
    db.session.add(nueva_orden)
    db.session.commit()

    for item in items_carrito:
        detalle = DetalleOrden(orden=nueva_orden, producto_id=item.producto_id, cantidad=item.cantidad,
                               precio_unitario=item.producto.precio)
        db.session.add(detalle)
        db.session.delete(item)

    db.session.commit()
    flash('Compra confirmada. Gracias por tu pedido.', 'success')

    return redirect(url_for('mis_ordenes'))


def float_format(value, decimals=1):
    try:
        value = float(value)
        return f"${value:.{decimals}f}"
    except (ValueError, TypeError):
        return value


app.jinja_env.filters['float_format'] = float_format

if __name__ == '__main__':
    app.run()
