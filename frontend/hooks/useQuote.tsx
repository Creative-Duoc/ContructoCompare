import { createContext, useContext, useState, ReactNode } from 'react';
import { QuoteItem, Producto, TiendaPrecio, getPrecioFinal, saveLocalCotizacion } from '../services/api';

interface QuoteCtx {
  items: QuoteItem[];
  addItem: (producto: Producto, tienda: TiendaPrecio) => void;
  removeItem: (idx: number) => void;
  updateQty: (idx: number, delta: number) => void;
  clearQuote: () => void;
  totalCLP: number;
  saveQuote: (nombre: string, userEmail: string, ufValue: number) => void;
}

const QuoteContext = createContext<QuoteCtx>({} as QuoteCtx);

export function QuoteProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<QuoteItem[]>([]);

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

  function clearQuote() { setItems([]); }

  const totalCLP = items.reduce((s, i) => s + getPrecioFinal(i.tienda_seleccionada) * i.cantidad, 0);

  // HU7: guardar cotización en localStorage
  function saveQuote(nombre: string, userEmail: string, ufValue: number) {
    saveLocalCotizacion(userEmail, {
      id: 'COT-' + Date.now(),
      nombre_proyecto: nombre,
      fecha_creacion: new Date().toLocaleDateString('es-CL'),
      items,
      total_clp: totalCLP,
      total_uf: parseFloat((totalCLP / ufValue).toFixed(4)),
    });
    clearQuote();
  }

  return (
    <QuoteContext.Provider value={{ items, addItem, removeItem, updateQty, clearQuote, totalCLP, saveQuote }}>
      {children}
    </QuoteContext.Provider>
  );
}

export const useQuote = () => useContext(QuoteContext);
