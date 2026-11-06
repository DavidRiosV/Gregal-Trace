// Mostrar u ocultar la contraseña con el botón del ojo.
// Cuando la contraseña se ve, el icono pasa a ojo tachado: pulsarlo la vuelve a ocultar.
document.querySelectorAll("[data-mostrar-contrasena]").forEach(function (boton) {
    boton.addEventListener("click", function () {
        var campo = document.getElementById(boton.dataset.mostrarContrasena);
        var mostrar = campo.type === "password";
        campo.type = mostrar ? "text" : "password";
        boton.classList.toggle("entrada__ojo--visible", mostrar);
        boton.setAttribute("aria-pressed", mostrar ? "true" : "false");
        boton.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
    });
});

// Pide confirmación antes de eliminar.
// Si se pulsa Cancelar devuelve false y el formulario no se envía.
function eliminar() {
    return confirm("¿Seguro que quieres eliminar este proyecto? Se borrarán también todos sus apuntes.");
}

function eliminar_apunte() {
    return confirm("¿Seguro que quieres eliminar este apunte?");
}

function eliminar_material() {
    return confirm("¿Seguro que quieres eliminar este material?");
}

// ---------------------------------------------------------------------------
// Selector deslizable de horas y minutos.
// Apartado «Horas de trabajo»: dos ruedas, horas de 0 a 24 y minutos 00, 15, 30 y 45.
// Lo elegido se escribe en el campo «cantidad» en horas con decimales (2 h 30 min = 2.50),
// que es lo que guarda Django.
// ---------------------------------------------------------------------------
var ALTO_OPCION = 40; // alto en píxeles de cada número de la rueda (igual que en el CSS)

function crearRueda(rueda, valores, alCambiar) {
    var elegido = 0;
    var espera = null;

    valores.forEach(function (valor, indice) {
        var opcion = document.createElement("div");
        opcion.className = "reloj__opcion";
        opcion.setAttribute("role", "option");
        opcion.textContent = valor < 10 && valores.length < 10 ? "0" + valor : valor;
        // Al pulsar un número, la rueda se desliza hasta él
        opcion.addEventListener("click", function () { elegir(indice, true); });
        rueda.appendChild(opcion);
    });

    function marcar(indice) {
        elegido = Math.max(0, Math.min(valores.length - 1, indice));
        rueda.querySelectorAll(".reloj__opcion").forEach(function (opcion, i) {
            opcion.classList.toggle("reloj__opcion--elegida", i === elegido);
            opcion.setAttribute("aria-selected", i === elegido ? "true" : "false");
        });
    }

    function elegir(indice, suave) {
        marcar(indice);
        rueda.scrollTo({ top: elegido * ALTO_OPCION, behavior: suave ? "smooth" : "auto" });
        alCambiar();
    }

    // Al deslizar con el dedo o la rueda del ratón: cuando se para, se queda con el número del centro
    rueda.addEventListener("scroll", function () {
        clearTimeout(espera);
        espera = setTimeout(function () {
            var indice = Math.round(rueda.scrollTop / ALTO_OPCION);
            if (indice !== elegido) {
                marcar(indice);
                alCambiar();
            }
        }, 90);
    });

    // Con el teclado: flechas arriba y abajo
    rueda.addEventListener("keydown", function (evento) {
        if (evento.key === "ArrowDown") { evento.preventDefault(); elegir(elegido + 1, true); }
        if (evento.key === "ArrowUp") { evento.preventDefault(); elegir(elegido - 1, true); }
    });

    return {
        valor: function () { return valores[elegido]; },
        elegir: elegir
    };
}

// Cada selector de horas de la página: escribe en el campo oculto «cantidad» del mismo formulario
document.querySelectorAll("[data-reloj]").forEach(function (reloj) {
    var cantidad = reloj.closest("form").querySelector("input[name=cantidad]");
    var listaHoras = [];
    for (var h = 0; h <= 24; h++) { listaHoras.push(h); }
    var listaMinutos = [0, 15, 30, 45];

    var horas = crearRueda(reloj.querySelector("[data-reloj-horas]"), listaHoras, escribir);
    var minutos = crearRueda(reloj.querySelector("[data-reloj-minutos]"), listaMinutos, escribir);

    function escribir() {
        var h = horas.valor();
        var m = minutos.valor();
        // Como mucho 24 h justas
        if (h === 24 && m !== 0) { minutos.elegir(0, true); m = 0; }
        cantidad.value = (h + m / 60).toFixed(2);
    }

    // Coloca las ruedas en lo que ya hubiera (1 h al empezar, o el valor al editar)
    var valor = parseFloat(String(cantidad.value).replace(",", ".")) || 1;
    var horaInicial = Math.min(24, Math.floor(valor));
    horas.elegir(horaInicial, false);
    minutos.elegir(Math.round((valor - horaInicial) * 4) % 4, false);
    escribir();
});

// Al elegir un material de la lista, se escribe su unidad junto a la cantidad (m, ud, kg...)
document.querySelectorAll("[data-opciones-material]").forEach(function (formulario) {
    var unidad = formulario.querySelector("[data-unidad-cantidad]");
    function poner() {
        var elegido = formulario.querySelector("input[name=material]:checked");
        unidad.textContent = elegido ? elegido.dataset.unidad : "";
    }
    formulario.addEventListener("change", poner);
    poner();
});

// En el móvil los botones de familia y tipo van en una fila que se desliza:
// se coloca la fila para que se vea el botón elegido.
document.querySelectorAll(".familias").forEach(function (fila) {
    var activo = fila.querySelector(".familia--activa");
    if (activo && fila.scrollWidth > fila.clientWidth) {
        fila.scrollLeft = activo.offsetLeft - fila.offsetLeft - 16;
    }
});
