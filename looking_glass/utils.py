import numpy as np
def db_to_lin(x_db: float) -> float:
    return 10.0**(x_db/10.0)
