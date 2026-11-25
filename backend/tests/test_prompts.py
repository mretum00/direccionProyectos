from services.prompts import construir_prompt


def test_prompt_exige_fidelidad_a_ramas_condicionales_de_procedimientos():
    prompt = construir_prompt(
        mensaje_original="¿Cómo se comprueba el componente?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "conserva el orden de los pasos" in prompt
    assert "cada rama SI/ENTONCES" in prompt
    assert "No conviertas varios casos en una regla general" in prompt
    assert "No conviertas el umbral de activación de un DTC en una instrucción de parada" in prompt
    assert "no inventes una respuesta para completar el intervalo" in prompt


def test_perfil_usuario_no_recibe_instrucciones_de_taller():
    prompt = construir_prompt(
        mensaje_original="¿Cómo reviso la bomba CMP-02?",
        fragmentos=[],
        perfil="user",
        version="V2.0",
    )

    assert "No conviertas procedimientos de taller en instrucciones para que el conductor los ejecute" in prompt
    assert "no active componentes desde HTM-SCAN" in prompt
    assert "no manipule componentes eléctricos o de alta tensión" in prompt
    assert "deriva la ejecución a personal cualificado" in prompt


def test_perfil_mecanico_no_equivale_a_habilitacion_automatica():
    prompt = construir_prompt(
        mensaje_original="¿Cómo reviso la bomba CMP-02?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "NO demuestra que la persona tenga una habilitación concreta" in prompt
    assert "comprueba siempre el apartado 'Perfil autorizado'" in prompt
    assert "no des por acreditada la cualificación por la selección del perfil" in prompt


def test_prompt_obliga_a_incluir_riesgos_epIs_herramientas_y_condiciones_documentados():
    prompt = construir_prompt(
        mensaje_original="¿Cómo reviso la bomba CMP-02?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "Perfil autorizado" in prompt
    assert "Riesgos" in prompt
    assert "Equipos de protección individual" in prompt
    assert "Herramientas necesarias" in prompt
    assert "Condiciones previas" in prompt
    assert "No califiques una intervención como rutinaria, inocua o sin riesgo" in prompt


def test_prompt_separa_los_pasos_prc_de_los_datos_de_diagnostico_dtc():
    prompt = construir_prompt(
        mensaje_original="¿Cómo reviso la bomba CMP-02?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "un PRC contiene los pasos del procedimiento" in prompt
    assert "No mezcles sus apartados" in prompt
    assert "continuidad eléctrica" in prompt
    assert "no la presentes como uno de los pasos numerados de PRC-003" in prompt


def test_prompt_no_convierte_las_causas_dtc_en_diagnostico_confirmado():
    prompt = construir_prompt(
        mensaje_original="¿Qué le pasa a CMP-02?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "posibilidades asociadas, no un diagnóstico confirmado" in prompt
    assert "no demuestra que esté averiado" in prompt
    assert "No afirmes que el sensor CMP-18 está defectuoso" in prompt


def test_prompt_conserva_las_ramas_condicionales_de_prc003_sin_generalizarlas():
    prompt = construir_prompt(
        mensaje_original="¿Cómo reviso la bomba CMP-02?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "en reposo, CMP-18 debe indicar 0 l/min" in prompt
    assert "8-14 l/min es conforme" in prompt
    assert "si el caudal es 0 l/min con la bomba activada" in prompt
    assert "si el caudal está entre 2 y 6 l/min" in prompt
    assert "No generalices «todo valor inferior a 8 l/min»" in prompt
    assert "no especifica una acción para ese caso" in prompt


def test_prompt_distingue_htm0202_de_htm0203():
    prompt = construir_prompt(
        mensaje_original="¿Qué significa HTM-0202?",
        fragmentos=[],
        perfil="mechanic",
        version="V2.0",
    )

    assert "HTM-0202 y HTM-0203 son entradas DTC distintas" in prompt
    assert "<2 l/min" in prompt
    assert "2-6 l/min" in prompt
    assert "No combines sus umbrales" in prompt


def test_perfil_usuario_no_recibe_diagnosticos_posibles_como_confirmados():
    prompt = construir_prompt(
        mensaje_original="¿Cómo reviso la bomba CMP-02?",
        fragmentos=[],
        perfil="user",
        version="V2.0",
    )

    assert "evita la sección «CAUSAS POSIBLES»" in prompt
    assert "no es un diagnóstico confirmado" in prompt
    assert "No des criterios de reparación" in prompt
