import { createContext, useContext, useState, ReactNode } from 'react';
import { QuoteItem, Producto, TiendaPrecio, getPrecioFinal, createQuote } from '../services/api';

interface QuoteCtx {
  items: QuoteItem[];
  addItem: (producto: Producto, tienda: TiendaPrecio) => void;
  removeItem: (idx: number) => void;
  updateQty: (idx: number, delta: number) => void;
  clearQuote: () => void;
  setItems: (items: QuoteItem[]) => void;
  totalCLP: number;
  saveQuote: (nombre: string) => Promise<{ success: boolean; error?: string }>;
  activeQuoteId: number | null;
  setActiveQuoteId: (id: number | null) => void;
  initialSnapshot: string;
  setInitialSnapshot: (snapshot: string) => void;
}

const QuoteContext = createContext<QuoteCtx>({} as QuoteCtx);

export const serializeQuoteItems = (currentItems: QuoteItem[]) => {
  return JSON.stringify(currentItems.map(i => ({
    id: i.producto.id,
    store: i.tienda_seleccionada.tienda,
    qty: i.cantidad
  })));
};

export function QuoteProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<QuoteItem[]>([]);
  const [activeQuoteId, setActiveQuoteId] = useState<number | null>(null);
  const [initialSnapshot, setInitialSnapshot] = useState<string>('');

  function addItem(producto: Producto, tienda: TiendaPrecio) {
    setItems(prev => {
      const existing = prev.findIndex(
        i => i.producto.id === producto.id && i.tienda_seleccionada.tienda === tienda.tienda
      );
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = { ...updated[existing], cantidad: updated[existing].cantidad + 1 };
        return updated;
      }
      return [...prev, { producto, tienda_seleccionada: tienda, cantidad: 1 }];
    });
  }

  function removeItem(idx: number) {
    setItems(prev => prev.filter((_, i) => i !== idx));
  }

  // HU5: no negativas, mínimo 1
  function updateQty(idx: number, delta: number) {
    setItems(prev => {
      const updated = [...prev];
      const newQty = updated[idx].cantidad + delta;
      if (newQty < 1) return prev;
      updated[idx] = { ...updated[idx], cantidad: newQty };
      return updated;
    });
  }

  function clearQuote() { 
    setItems([]); 
    setActiveQuoteId(null);
    setInitialSnapshot('');
  }

  function setItemsFromQuote(nextItems: QuoteItem[]) {
    setItems(nextItems);
  }

  const totalCLP = items.reduce((s, i) => s + getPrecioFinal(i.tienda_seleccionada) * i.cantidad, 0);

  async function saveQuote(nombre: string) {
    try {
      await createQuote(nombre, items);
      clearQuote();
      return { success: true };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  }

  return (
    <QuoteContext.Provider value={{ 
      items, addItem, removeItem, updateQty, clearQuote, 
      setItems: setItemsFromQuote, totalCLP, saveQuote, 
      activeQuoteId, setActiveQuoteId,
      initialSnapshot, setInitialSnapshot
    }}>
      {children}
    </QuoteContext.Provider>
  );
}

export const useQuote = () => useContext(QuoteContext);
