# vectorstores/store_utils.py
from .base_store import BaseVectorStore

def prepare_store(store: BaseVectorStore, re_process_data: bool) -> None:
    """
    If an index exists and re_process_data == False => load it.
    Else => drop and create a fresh one.
    """
    if store.exists() and not re_process_data:
        store.load()
    else:
        store.drop()
        store.create()
