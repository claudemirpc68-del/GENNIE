import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gennie

print("modulo:", gennie.__file__)
print("atributos:", [a for a in dir(gennie) if not a.startswith("_")])
