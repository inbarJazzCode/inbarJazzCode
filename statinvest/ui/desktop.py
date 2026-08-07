"""Minimal Tkinter desktop UI built on the shared service layer.

Tkinter may be unavailable in headless environments; ``run_desktop`` degrades
gracefully with a clear message instead of crashing. The UI uses the *same*
:class:`AnalysisService` as the Streamlit app, so normalization, database and
provider logic are identical and writes are not duplicated.
"""

from __future__ import annotations

from statinvest.config import APP_NAME, DISCLAIMER


def run_desktop() -> int:
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except Exception as exc:
        print(f"Desktop UI unavailable (Tkinter not installed): {exc}")
        print("Use the Streamlit UI instead: python main.py streamlit")
        return 1

    from statinvest.service import AnalysisService

    service = AnalysisService(provider_name="synthetic")

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("640x420")

    ttk.Label(root, text=APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(pady=6)
    ttk.Label(root, text=DISCLAIMER, wraplength=600, foreground="#555").pack(pady=2)

    frm = ttk.Frame(root)
    frm.pack(pady=8)
    ttk.Label(frm, text="Symbol:").grid(row=0, column=0, padx=4)
    entry = ttk.Entry(frm, width=20)
    entry.insert(0, "AAPL")
    entry.grid(row=0, column=1, padx=4)

    output = tk.Text(root, height=14, width=76)
    output.pack(pady=8)

    def fetch():
        sym = entry.get()
        try:
            result = service.fetch_symbol(sym, persist=True)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        md = result["market_data"]
        output.delete("1.0", tk.END)
        output.insert(tk.END, f"Symbol       : {md['symbol']}\n")
        output.insert(tk.END, f"Asset type   : {md['asset_type']}\n")
        output.insert(tk.END, f"Status       : {md['data_status']}\n")
        output.insert(tk.END, f"Price (norm) : {md['normalized_price']} "
                              f"{md['normalized_currency']}\n")
        output.insert(tk.END, f"Raw price    : {md['raw_price']} {md['raw_currency']}\n")
        output.insert(tk.END, f"Norm rule    : {md['normalization_rule']}\n")
        output.insert(tk.END, f"Trailing P/E : {md['trailing_pe']}\n")
        output.insert(tk.END, f"Saved to DB  : {result['persisted']}\n")

    ttk.Button(frm, text="Fetch & save", command=fetch).grid(row=0, column=2, padx=4)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_desktop())
