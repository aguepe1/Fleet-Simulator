# interfaz_simulador.py

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math
import numpy as np

import FlotaReserva as sim
from FlotaReserva import get_discrete_weibull_pmf, weibull_hazard_rate

plt.style.use('seaborn-v0_8-whitegrid')


class SimuladorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simulador de Flota v12.2 - Corrección Final")
        self.geometry("1600x900")

        self.style = ttk.Style(self)
        self.style.configure('Valid.TEntry', fieldbackground='white')
        self.style.configure('Invalid.TEntry', fieldbackground='#ffdddd')

        self.PREVIEW_PARAM_KEYS = {"FORMA_BETA_REPARACION_DISCRETA", "REPARACION_MEDIA", "FORMA_BETA_MNT_DISCRETA",
                                   "MNT_MEDIO", "FORMA_K_FALLA", "DISPONIBILIDAD"}
        self.params = sim.default_params.copy()

        self.param_vars = {}
        self.widget_map = {}
        self.hourly_req_widgets = []
        self.maintenance_rule_rows = []

        self.results_queue = queue.Queue()
        self.stop_event = threading.Event()

        canvas = tk.Canvas(self);
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview);
        scrollable_frame = ttk.Frame(canvas, padding="10")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw");
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.Y, expand=False);
        scrollbar.pack(side=tk.LEFT, fill="y")
        output_frame = ttk.Frame(self, padding="10");
        output_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._create_control_panel(scrollable_frame)
        self._create_output_panel(output_frame)
        self._update_preview_plots()
        self._run_all_validations()

    def _create_control_panel(self, parent):
        sim_controls_frame = ttk.LabelFrame(parent, text="Controles", padding="10");
        sim_controls_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
        self.run_button = ttk.Button(sim_controls_frame, text="▶ Iniciar Búsqueda",
                                     command=self.start_simulation_thread);
        self.run_button.pack(fill=tk.X, expand=True, pady=2)
        self.stop_button = ttk.Button(sim_controls_frame, text="■ Detener Simulación", command=self.request_stop,
                                      state='disabled');
        self.stop_button.pack(fill=tk.X, expand=True, pady=2)
        self.validation_status_label = ttk.Label(sim_controls_frame, text="", font=("Helvetica", 10, "bold"));
        self.validation_status_label.pack(fill=tk.X, expand=True, pady=5)

        general_frame = ttk.LabelFrame(parent, text="Configuración General", padding="10");
        general_frame.pack(fill=tk.X, expand=True, padx=5, pady=5);
        self._create_entry(general_frame, "TRENES_OPERATIVOS_REQUERIDOS", "Trenes operativos:");
        self._create_entry(general_frame, "NIVEL_SERVICIO_DESEADO", "Objetivo de Servicio (0-1):");
        self._create_entry(general_frame, "NUM_SIMULACIONES", "Nº de simulaciones:");
        self._create_entry(general_frame, "DIAS_POR_SIMULACION", "Días por simulación:")
        falla_frame = ttk.LabelFrame(parent, text="Parámetros de Falla", padding="10");
        falla_frame.pack(fill=tk.X, expand=True, padx=5, pady=5);
        self._create_entry(falla_frame, "DISPONIBILIDAD", "Disponibilidad (0-1):");
        self._create_entry(falla_frame, "FORMA_K_FALLA", "Forma Falla (k > 0):")

        mnt_policy_frame = ttk.LabelFrame(parent, text="Política de Mantenimiento Flexible", padding="10");
        mnt_policy_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
        self.maintenance_rows_frame = ttk.Frame(mnt_policy_frame);
        self.maintenance_rows_frame.pack(fill=tk.X, expand=True)
        add_button = ttk.Button(mnt_policy_frame, text="✚ Añadir Regla", command=self._add_maintenance_row);
        add_button.pack(pady=5)
        self.prob_status_label = ttk.Label(mnt_policy_frame, text="");
        self.prob_status_label.pack(anchor="w", pady=(5, 0))
        self._add_maintenance_row(trains_val="1", prob_val="70");
        self._add_maintenance_row(trains_val="2", prob_val="25");
        self._add_maintenance_row(trains_val="3", prob_val="5")

        mnt_params_frame = ttk.LabelFrame(parent, text="Parámetros de Duración del MNT", padding="10");
        mnt_params_frame.pack(fill=tk.X, expand=True, padx=5, pady=5);
        self._create_entry(mnt_params_frame, "MNT_MEDIO", "Media de MNT (días, entero):");
        self._create_entry(mnt_params_frame, "FORMA_BETA_MNT_DISCRETA", "Forma MNT (β > 0):")
        rep_frame = ttk.LabelFrame(parent, text="Parámetros de Reparación", padding="10");
        rep_frame.pack(fill=tk.X, expand=True, padx=5, pady=5);
        self._create_entry(rep_frame, "REPARACION_MEDIA", "Media de reparación (días, entero):");
        self._create_entry(rep_frame, "FORMA_BETA_REPARACION_DISCRETA", "Forma Reparación (β > 0):")

        req_frame = ttk.LabelFrame(parent, text="Requisitos de Trenes por Hora", padding="10");
        req_frame.pack(fill=tk.X, expand=True, padx=5, pady=5)
        for i in range(24):
            ttk.Label(req_frame, text=f"{i:02d}:00 - {i:02d}:59").grid(row=i, column=0, sticky="w", pady=1)
            var = tk.StringVar(value=str(self.params["REQUISITOS_TRENES_HORA"][i]))
            entry = tk.Entry(req_frame, textvariable=var, width=6, relief='sunken', borderwidth=1);
            entry.grid(row=i, column=1, sticky="ew", pady=1, padx=5)
            self.hourly_req_widgets.append({'var': var, 'widget': entry})
            var.trace_add("write", self._run_all_validations)

    def _create_entry(self, parent, key, text):
        frame = ttk.Frame(parent);
        frame.pack(fill=tk.X, expand=True, pady=2);
        ttk.Label(frame, text=text, width=32).pack(side=tk.LEFT)
        var = tk.StringVar(value=str(self.params[key]));
        self.param_vars[key] = var
        entry = tk.Entry(frame, textvariable=var, relief='sunken', borderwidth=1);
        entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.widget_map[key] = entry
        var.trace_add("write", self._run_all_validations)

    def _add_maintenance_row(self, trains_val="", prob_val=""):
        row_frame = ttk.Frame(self.maintenance_rows_frame);
        row_frame.pack(fill=tk.X, pady=2)
        ttk.Label(row_frame, text="Nº Trenes:").pack(side=tk.LEFT, padx=(0, 5));
        train_var = tk.StringVar(value=trains_val);
        train_entry = tk.Entry(row_frame, textvariable=train_var, width=6, relief='sunken', borderwidth=1);
        train_entry.pack(side=tk.LEFT);
        train_var.trace_add("write", self._run_all_validations)
        ttk.Label(row_frame, text="Prob. (%):").pack(side=tk.LEFT, padx=(10, 5));
        prob_var = tk.StringVar(value=prob_val);
        prob_entry = tk.Entry(row_frame, textvariable=prob_var, width=9, relief='sunken', borderwidth=1);
        prob_entry.pack(side=tk.LEFT);
        prob_var.trace_add("write", self._run_all_validations)
        remove_button = ttk.Button(row_frame, text="🗑️", width=3,
                                   command=lambda r=row_frame: self._remove_maintenance_row(r));
        remove_button.pack(side=tk.RIGHT, padx=(10, 0))
        self.maintenance_rule_rows.append(
            {'train_var': train_var, 'prob_var': prob_var, 'frame': row_frame, 'train_widget': train_entry,
             'prob_widget': prob_entry})
        self._run_all_validations()

    def _remove_maintenance_row(self, row_to_remove):
        row_data = next((data for data in self.maintenance_rule_rows if data['frame'] == row_to_remove), None)
        if row_data: self.maintenance_rule_rows.remove(row_data)
        row_to_remove.destroy();
        self._run_all_validations()

    def _set_widget_validity(self, widget, is_valid):
        color = 'white' if is_valid else '#ffdddd'
        if isinstance(widget, tk.Entry):
            widget.config(bg=color)

    def _run_all_validations(self, *args):
        is_form_fully_valid = True
        try:
            trenes_operativos = int(self.param_vars["TRENES_OPERATIVOS_REQUERIDOS"].get())
            is_valid_trenes_op = trenes_operativos > 0
            self._set_widget_validity(self.widget_map["TRENES_OPERATIVOS_REQUERIDOS"], is_valid_trenes_op)
            if not is_valid_trenes_op: is_form_fully_valid = False
            params_to_validate = {
                "NIVEL_SERVICIO_DESEADO": lambda v: 0 <= v <= 1, "DISPONIBILIDAD": lambda v: 0 <= v <= 1,
                "FORMA_K_FALLA": lambda v: v > 0, "FORMA_BETA_REPARACION_DISCRETA": lambda v: v > 0,
                "FORMA_BETA_MNT_DISCRETA": lambda v: v > 0, "REPARACION_MEDIA": lambda v: v > 0 and v == int(v),
                "MNT_MEDIO": lambda v: v > 0 and v == int(v)
            }
            for key, rule in params_to_validate.items():
                widget = self.widget_map[key];
                val_str = self.param_vars[key].get();
                val = float(val_str)
                is_valid = rule(val);
                self._set_widget_validity(widget, is_valid)
                if not is_valid: is_form_fully_valid = False
            for item in self.hourly_req_widgets:
                val = int(item['var'].get());
                is_valid = 0 <= val <= trenes_operativos
                self._set_widget_validity(item['widget'], is_valid)
                if not is_valid: is_form_fully_valid = False
            total_prob = 0
            if not self.maintenance_rule_rows: is_form_fully_valid = False
            for row in self.maintenance_rule_rows:
                trains = int(row['train_var'].get());
                prob = float(row['prob_var'].get());
                total_prob += prob
                is_trains_valid = 0 < trains <= trenes_operativos;
                is_prob_valid = 0 <= prob <= 100
                self._set_widget_validity(row['train_widget'], is_trains_valid);
                self._set_widget_validity(row['prob_widget'], is_prob_valid)
                if not is_trains_valid or not is_prob_valid: is_form_fully_valid = False
            if not math.isclose(total_prob, 100.0):
                is_form_fully_valid = False
                self.prob_status_label.config(text=f"Probabilidad Total: {total_prob:.1f}% (DEBE SER 100%)",
                                              foreground="red")
            else:
                self.prob_status_label.config(text=f"Probabilidad Total: {total_prob:.1f}%", foreground="green")
        except (ValueError, KeyError):
            is_form_fully_valid = False
        if is_form_fully_valid:
            self.validation_status_label.config(text="✅ Todos los parámetros son válidos.", foreground="green")
            self.run_button.config(state="normal")
        else:
            self.validation_status_label.config(text="❌ Hay errores en los parámetros (campos en rojo).",
                                                foreground="red")
            self.run_button.config(state="disabled")
        self._update_preview_plots()
        return is_form_fully_valid

    def start_simulation_thread(self):
        self.validation_status_label.config(text="Ejecutando simulación...");

        is_valid, trains_list, probs_list = self._get_maintenance_policy_data()
        self.params = {key: float(var.get()) if '.' in var.get() else int(var.get()) for key, var in
                       self.param_vars.items()}
        self.params["REQUISITOS_TRENES_HORA"] = [int(item['var'].get()) for item in self.hourly_req_widgets];
        self.params["LISTA_MNT"] = trains_list;
        self.params["P_MNT"] = probs_list
        self._clear_plots(clear_previews=False)
        self.run_button.config(state='disabled');
        self.stop_button.config(state='normal');
        self.stop_event.clear()
        self.update_progress("Iniciando búsqueda...\n", [])
        thread = threading.Thread(target=self.run_simulation_in_background, args=(self.update_progress,));
        thread.daemon = True;
        thread.start()
        self.after(100, self.check_queue)

    def _get_maintenance_policy_data(self):
        trains = [];
        probs = []
        for row in self.maintenance_rule_rows:
            trains.append(int(row['train_var'].get()));
            probs.append(float(row['prob_var'].get()))
        return True, trains, [p / 100.0 for p in probs]

    def _create_output_panel(self, parent):
        notebook = ttk.Notebook(parent);
        notebook.pack(fill=tk.BOTH, expand=True);
        log_tab = ttk.Frame(notebook)
        self.log_text = scrolledtext.ScrolledText(log_tab, wrap=tk.WORD, state='disabled', font=("Courier New", 10));
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        notebook.add(log_tab, text="Resumen y Log de Búsqueda");
        plot1_tab = ttk.Frame(notebook);
        self.fig1, self.ax1 = plt.subplots();
        self.canvas1 = FigureCanvasTkAgg(self.fig1, master=plot1_tab);
        self.canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        notebook.add(plot1_tab, text="Historial de Búsqueda");
        plot2_tab = ttk.Frame(notebook);
        self.fig2, self.axes2 = plt.subplots(1, 2, sharey=True);
        self.fig2.tight_layout(pad=3.0);
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=plot2_tab);
        self.canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        notebook.add(plot2_tab, text="Distribuciones de Paro");
        plot3_tab = ttk.Frame(notebook);
        self.fig3, self.ax3 = plt.subplots();
        self.canvas3 = FigureCanvasTkAgg(self.fig3, master=plot3_tab);
        self.canvas3.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        notebook.add(plot3_tab, text="Tasa de Falla (Desgaste)")

    def _clear_plots(self, clear_previews=True):
        self.ax1.clear();
        self.ax1.set_title("Historial de Búsqueda");
        self.canvas1.draw()
        if clear_previews: self._update_preview_plots()

    def request_stop(self):
        # ✅ CORREGIDO: Usar el nuevo nombre de la variable
        self.validation_status_label.config(text="Deteniendo simulación...")
        self.stop_event.set();
        self.stop_button.config(state='disabled')

    def run_simulation_in_background(self, progress_callback):
        try:
            results = sim.run_full_analysis(self.params, self.stop_event, progress_callback);
            self.results_queue.put(results)
        except Exception as e:
            self.results_queue.put(f"ERROR INESPERADO: {e}")

    def check_queue(self):
        try:
            result = self.results_queue.get_nowait()
            safe_result = {}
            if isinstance(result, dict):
                safe_result['plot_history'] = result.get('plot_history', result.get('history', []));
                safe_result['log_text'] = result.get('log_text', 'Log no disponible.');
                safe_result['stopped'] = result.get('stopped', False);
                safe_result['trenes_optimos'] = result.get('trenes_optimos', -1)
                safe_result['plot_reparacion'] = result.get('plot_reparacion');
                safe_result['plot_mnt'] = result.get('plot_mnt');
                safe_result['plot_falla'] = result.get('plot_falla')
            else:
                messagebox.showerror("Error de Simulación", str(result))
                # ✅ CORREGIDO: Usar el nuevo nombre de la variable
                self.validation_status_label.config(text="Error durante la simulación.")
                self.reset_ui_state();
                return
            self.update_gui_with_results(safe_result)
            if safe_result['stopped']:
                # ✅ CORREGIDO: Usar el nuevo nombre de la variable
                self.validation_status_label.config(text="Búsqueda detenida por el usuario.")
            else:
                # ✅ CORREGIDO: Usar el nuevo nombre de la variable
                self.validation_status_label.config(text="Búsqueda completada con éxito.")
            self.reset_ui_state()
        except queue.Empty:
            self.after(100, self.check_queue)

    def reset_ui_state(self):
        self.run_button.config(state='normal');
        self.stop_button.config(state='disabled')
        self._run_all_validations()

    def update_progress(self, text, history):
        self.log_text.config(state='normal');
        self.log_text.delete('1.0', tk.END);
        self.log_text.insert('1.0', text);
        self.log_text.see(tk.END);
        self.log_text.config(state='disabled')
        self.update_history_plot({"plot_history": history})

    def update_history_plot(self, results):
        self.ax1.clear();
        history = results.get("plot_history", [])
        if not history: self.canvas1.draw();return
        x_vals, y_vals = zip(*history)
        try:
            objetivo = float(self.param_vars["NIVEL_SERVICIO_DESEADO"].get())
        except ValueError:
            objetivo = 0.99  # Valor por defecto si la entrada es inválida
        self.ax1.plot(x_vals, y_vals, marker='o', linestyle='--', color='gray', label='Intentos')
        for x, y in history:
            color = 'green' if y >= objetivo else 'red'
            self.ax1.scatter(x, y, color=color, zorder=5)
        self.ax1.axhline(y=objetivo, color='darkorange', linestyle=':', label=f'Objetivo ({objetivo:.2%})')
        if results.get("trenes_optimos", -1) != -1:
            self.ax1.axvline(x=results["trenes_optimos"], color='blue', linestyle='-',
                             label=f'Flota Mínima: {results["trenes_optimos"]}')
        self.ax1.set_title('Historial de Búsqueda de Flota', fontsize=14, fontweight='bold');
        self.ax1.set_xlabel('Nº de Trenes de Reserva Probados');
        self.ax1.set_ylabel('Nivel de Servicio Alcanzado');
        self.ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}'));
        self.ax1.legend();
        self.ax1.grid(True)
        self.canvas1.draw()

    def update_gui_with_results(self, results):
        self.update_progress(results["log_text"], results["plot_history"])
        if not results.get("stopped") and results.get('plot_reparacion'):
            self.axes2[0].clear();
            self.axes2[1].clear()
            data_rep = results["plot_reparacion"];
            self.axes2[0].bar(data_rep["x"], data_rep["y"],
                              label=rf'$\beta$={data_rep["beta"]}, \eta$={data_rep["eta"]:.2f}', color='darkorange');
            self.axes2[0].set_title('Tiempo de Reparación');
            self.axes2[0].set_xlabel('Días');
            self.axes2[0].set_ylabel('Probabilidad');
            self.axes2[0].set_xticks(data_rep["x"]);
            self.axes2[0].legend()
            data_mnt = results["plot_mnt"];
            self.axes2[1].bar(data_mnt["x"], data_mnt["y"],
                              label=rf'$\beta$={data_mnt["beta"]}, \eta$={data_mnt["eta"]:.2f}', color='skyblue');
            self.axes2[1].set_title('Tiempo de Mantenimiento');
            self.axes2[1].set_xlabel('Días');
            self.axes2[1].set_xticks(data_mnt["x"]);
            self.axes2[1].legend()
            self.fig2.suptitle('Distribuciones (Resultado Final)', fontsize=14, fontweight='bold');
            self.canvas2.draw()
            self.ax3.clear()
            data_falla = results["plot_falla"];
            self.ax3.plot(data_falla["x"], data_falla["y"], marker='.', linestyle='-', color='crimson',
                          label='Tasa de Riesgo Diaria');
            self.ax3.axvline(x=data_falla["mttf"], color='darkgreen', linestyle='--',
                             label=f'MTTF = {data_falla["mttf"]} días');
            self.ax3.set_title('Probabilidad de Falla por Desgaste', fontsize=14, fontweight='bold');
            self.ax3.set_xlabel('Antigüedad (días)');
            self.ax3.set_ylabel('Probabilidad de Fallar');
            self.ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}'));
            self.ax3.legend();
            self.ax3.grid(True)
            self.canvas3.draw()

    def _update_preview_plots(self, *args):
        try:
            params = {key: float(var.get()) if '.' in var.get() else int(var.get()) for key, var in
                      self.param_vars.items()}
            escala_eta_reparacion = params["REPARACION_MEDIA"] / math.gamma(
                1 + 1 / params["FORMA_BETA_REPARACION_DISCRETA"]);
            x_range_rep = np.arange(1, 11);
            pmf_reparacion = get_discrete_weibull_pmf(x_range_rep, params["FORMA_BETA_REPARACION_DISCRETA"],
                                                      escala_eta_reparacion)
            escala_eta_mnt = params["MNT_MEDIO"] / math.gamma(1 + 1 / params["FORMA_BETA_MNT_DISCRETA"]);
            x_range_mnt = np.arange(1, 11);
            pmf_mnt = get_discrete_weibull_pmf(x_range_mnt, params["FORMA_BETA_MNT_DISCRETA"], escala_eta_mnt)
            tasa_fallo = 1 - params["DISPONIBILIDAD"];
            mttf_falla = round(1 / tasa_fallo, 2) if tasa_fallo > 0 else float('inf');
            escala_lambda_falla = mttf_falla / math.gamma(1 + 1 / params["FORMA_K_FALLA"]);
            edades = np.arange(1, 31);
            tasas_de_falla = [weibull_hazard_rate(t, params["FORMA_K_FALLA"], escala_lambda_falla) for t in edades]
            self.axes2[0].clear();
            self.axes2[1].clear()
            self.axes2[0].bar(x_range_rep, pmf_reparacion,
                              label=rf'$\beta$={params["FORMA_BETA_REPARACION_DISCRETA"]}, \eta$={escala_eta_reparacion:.2f}',
                              color='darkorange');
            self.axes2[0].set_title('Tiempo de Reparación');
            self.axes2[0].set_xlabel('Días');
            self.axes2[0].set_ylabel('Probabilidad');
            self.axes2[0].set_xticks(x_range_rep);
            self.axes2[0].legend()
            self.axes2[1].bar(x_range_mnt, pmf_mnt,
                              label=rf'$\beta$={params["FORMA_BETA_MNT_DISCRETA"]}, \eta$={escala_eta_mnt:.2f}',
                              color='skyblue');
            self.axes2[1].set_title('Tiempo de Mantenimiento');
            self.axes2[1].set_xlabel('Días');
            self.axes2[1].set_xticks(x_range_mnt);
            self.axes2[1].legend()
            self.fig2.suptitle('Distribuciones de Paro (Previsualización)', fontsize=14, fontweight='bold');
            self.canvas2.draw()
            self.ax3.clear()
            self.ax3.plot(edades, tasas_de_falla, marker='.', linestyle='-', color='crimson',
                          label='Tasa de Riesgo Diaria')
            if mttf_falla != float('inf'):
                self.ax3.axvline(x=mttf_falla, color='darkgreen', linestyle='--', label=f'MTTF = {mttf_falla} días')
            self.ax3.set_title('Probabilidad de Falla por Desgaste', fontsize=14, fontweight='bold');
            self.ax3.set_xlabel('Antigüedad (días)');
            self.ax3.set_ylabel('Probabilidad de Fallar');
            self.ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}'));
            self.ax3.legend();
            self.ax3.grid(True)
            self.canvas3.draw()
        except(ValueError, ZeroDivisionError, TypeError, KeyError):
            pass


if __name__ == "__main__":
    app = SimuladorApp()
    app.mainloop()