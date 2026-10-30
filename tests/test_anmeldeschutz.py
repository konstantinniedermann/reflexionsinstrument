from app.anmeldeschutz import Anmeldeschutz


class Uhr:
    def __init__(self) -> None:
        self.jetzt = [0.0]

    def __call__(self) -> float:
        return self.jetzt[0]

    def weiter(self, sekunden: float) -> None:
        self.jetzt[0] += sekunden


def _schutz(**kwargs):
    uhr = Uhr()
    return uhr, Anmeldeschutz(uhr=uhr, **kwargs)


def test_fuenf_fehlversuche_sperren_namen():
    _, schutz = _schutz()
    for _ in range(4):
        schutz.fehlversuch("lp.anna", "1.1.1.1")
    assert not schutz.gesperrt("lp.anna", "1.1.1.1")
    schutz.fehlversuch("lp.anna", "1.1.1.1")
    assert schutz.gesperrt("lp.anna", "1.1.1.1")
    assert schutz.gesperrt("lp.anna", "2.2.2.2")


def test_gesperrt_zeichnet_nichts_auf():
    _, schutz = _schutz()
    for _ in range(10):
        schutz.gesperrt("lp.anna", "1.1.1.1")
    schutz.fehlversuch("lp.anna", "1.1.1.1")
    assert not schutz.gesperrt("lp.anna", "1.1.1.1")


def test_sperre_endet_nach_fenster():
    uhr, schutz = _schutz()
    for _ in range(5):
        schutz.fehlversuch("lp.anna", "1.1.1.1")
    assert schutz.gesperrt("lp.anna", "1.1.1.1")
    uhr.weiter(901)
    assert not schutz.gesperrt("lp.anna", "1.1.1.1")


def test_gleitendes_fenster():
    uhr, schutz = _schutz()
    schutz.fehlversuch("lp.anna", "a")
    uhr.weiter(600)
    for _ in range(4):
        schutz.fehlversuch("lp.anna", "a")
    assert schutz.gesperrt("lp.anna", "a")
    uhr.weiter(301)  # der erste Versuch (t=0) ist raus, 4 verbleiben
    assert not schutz.gesperrt("lp.anna", "a")
    schutz.fehlversuch("lp.anna", "a")
    assert schutz.gesperrt("lp.anna", "a")


def test_zwanzig_fehlversuche_pro_adresse():
    _, schutz = _schutz()
    for i in range(19):
        schutz.fehlversuch(f"name{i}", "1.1.1.1")
    assert not schutz.gesperrt("neu", "1.1.1.1")
    schutz.fehlversuch("name19", "1.1.1.1")
    assert schutz.gesperrt("neu", "1.1.1.1")
    assert not schutz.gesperrt("neu", "2.2.2.2")


def test_erfolg_loescht_namen_nicht_adresse():
    _, schutz = _schutz(max_pro_adresse=5)
    for _ in range(4):
        schutz.fehlversuch("lp.anna", "1.1.1.1")
    schutz.erfolg("lp.anna")
    assert not schutz.gesperrt("lp.anna", "2.2.2.2")
    schutz.fehlversuch("lp.anna", "1.1.1.1")
    assert schutz.gesperrt("andere", "1.1.1.1")


def test_name_unabhaengig_von_schreibweise():
    _, schutz = _schutz()
    for _ in range(3):
        schutz.fehlversuch("LP.Anna ", "a")
    for _ in range(2):
        schutz.fehlversuch("lp.anna", "b")
    assert schutz.gesperrt("  Lp.ANNA", "c")


def test_speicher_begrenzt():
    uhr, schutz = _schutz(max_schluessel=10)
    for i in range(50):
        uhr.weiter(1)
        schutz.fehlversuch("lp.anna", f"adresse{i}")
    assert len(schutz._eintraege) <= 10
