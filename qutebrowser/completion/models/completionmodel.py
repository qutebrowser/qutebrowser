from qutebrowser.completion.models import base
from qutebrowser.completion.models import common
from qutebrowser.completion.models.spawnflags import SpawnFlagsModel

class CompletionModel(base.BaseModel):
    def __init__(self, parent=None, text=""):
        super().__init__(parent)
        self._text = text
        self._categories = []

        self._load_models()

    def _load_models(self):
        # Add default categories here if needed

        # Inject spawn flag completions
        if self._text.startswith(":spawn ") and "--" in self._text:
            self.add_category("Spawn Flags", SpawnFlagsModel())

    def add_category(self, name, model):
        self._categories.append((name, model))

    def data(self, completion_type):
        results = []
        for name, model in self._categories:
            results.extend(model.data(completion_type))
        return results
