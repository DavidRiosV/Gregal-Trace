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

// Ventana de confirmación propia (en vez del confirm() del navegador).
// Cualquier botón con data-confirmar="texto" la abre antes de enviar su formulario.
// Usa la etiqueta <dialog> de HTML: showModal() la abre encima de la página y oscurece el fondo.
var ventana = document.createElement("dialog");
ventana.className = "confirmar";
ventana.innerHTML =
    '<h2 class="confirmar__titulo">¿Seguro que quieres eliminarlo?</h2>' +
    '<p class="confirmar__texto"></p>' +
    '<div class="confirmar__botones">' +
    '<button type="button" class="boton boton--secundario" data-cancelar>Cancelar</button>' +
    '<button type="button" class="boton boton--borrar" data-aceptar>Eliminar</button>' +
    '</div>';
document.body.appendChild(ventana);
var formularioPendiente = null;

document.querySelectorAll("[data-confirmar]").forEach(function (boton) {
    boton.addEventListener("click", function (evento) {
        evento.preventDefault();
        formularioPendiente = boton.form;
        ventana.querySelector(".confirmar__texto").textContent = boton.dataset.confirmar;
        ventana.showModal();
        ventana.querySelector("[data-cancelar]").focus();
    });
});
ventana.querySelector("[data-cancelar]").addEventListener("click", function () {
    ventana.close();
});
ventana.querySelector("[data-aceptar]").addEventListener("click", function () {
    ventana.close();
    if (formularioPendiente) {
        formularioPendiente.submit();
    }
});
// Pulsar fuera de la ventana también la cierra
ventana.addEventListener("click", function (evento) {
    if (evento.target === ventana) {
        ventana.close();
    }
});

// Avisos («Apuntado…», «Proyecto creado»...): se cierran solos a los 4 segundos.
// Si el ratón está encima, esperan; la X los cierra al momento.
document.querySelectorAll(".avisos .aviso").forEach(function (aviso) {
    var cerrar = document.createElement("button");
    cerrar.type = "button";
    cerrar.className = "aviso__cerrar";
    cerrar.setAttribute("aria-label", "Cerrar aviso");
    cerrar.textContent = "×";
    aviso.appendChild(cerrar);

    var temporizador;
    function ocultar() {
        aviso.classList.add("aviso--saliendo");
        setTimeout(function () { aviso.remove(); }, 300);
    }
    function programar() {
        temporizador = setTimeout(ocultar, 4000);
    }
    cerrar.addEventListener("click", ocultar);
    aviso.addEventListener("mouseenter", function () { clearTimeout(temporizador); });
    aviso.addEventListener("mouseleave", programar);
    programar();
});

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
document.querySelectorAll(".familias, .segmentos--desliza").forEach(function (fila) {
    var activo = fila.querySelector(".familia--activa, .segmento--activo");
    if (activo && fila.scrollWidth > fila.clientWidth) {
        fila.scrollLeft = activo.offsetLeft - fila.offsetLeft - 16;
    }
});

// Pestañas de abajo en el detalle del proyecto: Apuntes, Notas y Albaranes.
// Sin JavaScript se ven las tres seguidas; con él, solo la elegida. La elegida se guarda
// en la dirección (#notas) para que al recargar o volver de guardar siga abierta.
document.querySelectorAll("[data-pestanas]").forEach(function (bloque) {
    var botones = bloque.querySelectorAll("[data-pestana]");
    var nombres = Array.prototype.map.call(botones, function (b) { return b.dataset.pestana; });
    bloque.classList.add("pestanas-proyecto--activas");

    function abrir(nombre, moverPantalla) {
        botones.forEach(function (boton) {
            var elegida = boton.dataset.pestana === nombre;
            boton.classList.toggle("pestana-proyecto--activa", elegida);
            boton.setAttribute("aria-selected", elegida ? "true" : "false");
            document.getElementById(boton.dataset.pestana).hidden = !elegida;
        });
        if (moverPantalla) {
            bloque.scrollIntoView({ block: "start" });
        }
    }

    botones.forEach(function (boton) {
        boton.addEventListener("click", function (evento) {
            evento.preventDefault();
            abrir(boton.dataset.pestana, false);
            history.replaceState(null, "", "#" + boton.dataset.pestana);
        });
    });

    // Pestaña inicial: la de la dirección (#albaranes), la que manda Django si hay errores, o Apuntes
    var desdeDireccion = location.hash.slice(1);
    if (nombres.indexOf(desdeDireccion) !== -1) {
        abrir(desdeDireccion, true);
    } else {
        abrir(nombres.indexOf(bloque.dataset.pestanaInicial) !== -1 ? bloque.dataset.pestanaInicial : nombres[0],
              bloque.dataset.pestanaInicial && bloque.dataset.pestanaInicial !== "apuntes");
    }
});

// Subir albarán: muestra el nombre del PDF elegido y deja soltarlo arrastrándolo encima
document.querySelectorAll("[data-zona-pdf]").forEach(function (zona) {
    var entrada = zona.querySelector("input[type=file]");
    var texto = zona.querySelector("[data-zona-pdf-nombre]");
    var textoInicial = texto.textContent;

    function mostrar() {
        var archivo = entrada.files[0];
        texto.textContent = archivo ? archivo.name : textoInicial;
        zona.classList.toggle("zona-pdf--elegido", Boolean(archivo));
    }
    entrada.addEventListener("change", mostrar);

    ["dragenter", "dragover"].forEach(function (tipo) {
        zona.addEventListener(tipo, function (evento) {
            evento.preventDefault();
            zona.classList.add("zona-pdf--encima");
        });
    });
    ["dragleave", "drop"].forEach(function (tipo) {
        zona.addEventListener(tipo, function () { zona.classList.remove("zona-pdf--encima"); });
    });
    zona.addEventListener("drop", function (evento) {
        evento.preventDefault();
        if (evento.dataTransfer.files.length) {
            entrada.files = evento.dataTransfer.files;
            mostrar();
        }
    });
});

// App instalable: registra el service worker (/sw.js). Si el navegador no lo admite, no pasa nada.
if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/sw.js");
    });
}
