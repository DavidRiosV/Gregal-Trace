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

// Pide confirmación antes de eliminar (diapositiva 81).
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
