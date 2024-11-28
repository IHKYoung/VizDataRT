import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter.font as tkFont
import argparse
import threading
import time
import sys
import os

class VizDataRT:
    def __init__(self, csv_file, refresh_interval=0.5):
        self.csv_file = csv_file
        self.refresh_interval = refresh_interval  # in seconds
        self.running = False  # 初始状态为未运行
        self.metric = 'PSNR'  # Default metric to plot
        self.data = pd.DataFrame()
        self.image_names = []
        self.selected_images = []
        self.data_lock = threading.Lock()
        self.create_gui()
        if self.csv_file:
            self.load_initial_data()
            self.start_data_thread()
            self.running = True
        self.animate_plot()

    def create_gui(self):
        # Initialize the main window
        self.root = tk.Tk()
        self.root.title("VizDataRT: Real-Time Data Visualization")
        self.root.geometry("1600x1200")

        # 设置全局字体
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(size=16)
        self.root.option_add("*Font", default_font)

        # Create a main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create a frame for the controls at the top
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X)

        # Create a frame for the plot
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Configure grid weights for resizing
        control_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Metric selection
        ttk.Label(control_frame, text="Select Metric:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.metric_var = tk.StringVar(value='PSNR')
        self.metric_menu = ttk.OptionMenu(
            control_frame, self.metric_var, 'PSNR', *['PSNR', 'l1', 'ssim_loss', 'prior_loss', 'depth_loss'], command=self.update_metric)
        self.metric_menu.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # Image selection
        ttk.Label(control_frame, text="Select Image(s):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.NW)
        self.image_listbox = tk.Listbox(control_frame, selectmode=tk.MULTIPLE, exportselection=0)
        self.image_listbox.config(height=10)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(control_frame, orient=tk.VERTICAL, command=self.image_listbox.yview)
        self.image_listbox['yscrollcommand'] = scrollbar.set
        self.image_listbox.grid(row=1, column=1, padx=5, pady=5, sticky=tk.NSEW)
        scrollbar.grid(row=1, column=2, sticky=tk.NS)

        # Select All / Deselect All Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        self.select_all_button = ttk.Button(button_frame, text="Select All", command=self.select_all_images)
        self.select_all_button.pack(side=tk.LEFT, padx=5)
        self.deselect_all_button = ttk.Button(button_frame, text="Deselect All", command=self.deselect_all_images)
        self.deselect_all_button.pack(side=tk.LEFT, padx=5)

        # Sort Buttons
        sort_button_frame = ttk.Frame(control_frame)
        sort_button_frame.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        self.sort_asc_button = ttk.Button(sort_button_frame, text="Sort Ascending", command=lambda: self.sort_images(ascending=True))
        self.sort_asc_button.pack(side=tk.LEFT, padx=5)
        self.sort_desc_button = ttk.Button(sort_button_frame, text="Sort Descending", command=lambda: self.sort_images(ascending=False))
        self.sort_desc_button.pack(side=tk.LEFT, padx=5)

        # Refresh Interval
        ttk.Label(control_frame, text="Refresh Interval (s):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.refresh_var = tk.DoubleVar(value=self.refresh_interval)
        self.refresh_entry = ttk.Entry(control_frame, textvariable=self.refresh_var, width=10)
        self.refresh_entry.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)
        self.refresh_entry.bind("<Return>", self.update_refresh_interval)

        # Open CSV and Save Plot Buttons
        self.open_button = ttk.Button(control_frame, text="Open CSV", command=self.open_csv_file)
        self.open_button.grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)

        self.save_button = ttk.Button(control_frame, text="Save Plot", command=self.save_plot)
        self.save_button.grid(row=5, column=2, padx=5, pady=5, sticky=tk.E)

        # Pause/Resume Button
        self.pause_button = ttk.Button(control_frame, text="Pause", command=self.toggle_pause)
        self.pause_button.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)

        # Set up the matplotlib figure and axes in plot_frame
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Load initial data to populate image names
        if self.csv_file:
            self.load_initial_data()

    def open_csv_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.csv_file = file_path
            self.load_initial_data()
            print(f"Opened file: {self.csv_file}")
            # 如果之前未启动数据线程，则启动
            if not self.running:
                self.running = True
                self.start_data_thread()

    def save_plot(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if file_path:
            self.fig.savefig(file_path)
            print(f"Plot saved to {file_path}")

    def toggle_pause(self):
        if self.running:
            self.running = False
            self.pause_button.config(text="Resume")
        else:
            self.running = True
            self.pause_button.config(text="Pause")
            self.start_data_thread()

    def get_metric_columns(self):
        # Exclude 'image_name' from the list of metrics
        metric_columns = [col for col in self.data.columns if col != 'image_name']
        return metric_columns

    def load_initial_data(self):
        if not self.csv_file:
            return
        if os.path.isfile(self.csv_file):
            try:
                with self.data_lock:
                    self.data = pd.read_csv(self.csv_file)
                if 'image_name' not in self.data.columns:
                    messagebox.showerror("Error", "'image_name' column not found in CSV file.")
                    return
                self.image_names = self.data['image_name'].unique().tolist()
                self.image_listbox.delete(0, tk.END)
                for img_name in self.image_names:
                    self.image_listbox.insert(tk.END, img_name)
                # Update metric options
                metrics = self.get_metric_columns()
                self.metric_menu['menu'].delete(0, 'end')
                for metric in metrics:
                    self.metric_menu['menu'].add_command(label=metric, command=lambda m=metric: self.update_metric(m))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load data: {e}")
        else:
            messagebox.showerror("Error", f"File {self.csv_file} does not exist.")

    def refresh_images(self):
        # Refresh the list of images in the listbox
        self.load_initial_data()

    def update_metric(self, value):
        self.metric_var.set(value)
        self.metric = value
        self.ax.clear()  # Clear the plot to update with new metric

    def select_all_images(self):
        self.image_listbox.select_set(0, tk.END)

    def deselect_all_images(self):
        self.image_listbox.select_clear(0, tk.END)

    def sort_images(self, ascending=True):
        with self.data_lock:
            data_copy = self.data.copy()
        
        if self.metric not in data_copy.columns:
            print(f"Metric '{self.metric}' not found in data for sorting.")
            return

        # 根据平均值排序
        image_metrics = data_copy.groupby('image_name')[self.metric].mean().reset_index()
        # 根据最新值排序
        # image_metrics = data_copy.groupby('image_name').last().reset_index()
        image_metrics_sorted = image_metrics.sort_values(by=self.metric, ascending=ascending)
        sorted_image_names = image_metrics_sorted['image_name'].tolist()
        
        # 保存当前选择的图像
        selected_indices = self.image_listbox.curselection()
        selected_images = [self.image_listbox.get(i) for i in selected_indices]

        # 更新列表框
        self.image_listbox.delete(0, tk.END)
        for img_name in sorted_image_names:
            self.image_listbox.insert(tk.END, img_name)
        
        # 恢复已选择的图像
        for idx, img_name in enumerate(sorted_image_names):
            if img_name in selected_images:
                self.image_listbox.selection_set(idx)

    def update_refresh_interval(self, event=None):
        try:
            new_interval = float(self.refresh_var.get())
            if new_interval <= 0:
                raise ValueError
            self.refresh_interval = new_interval
            print(f"Refresh interval updated to {self.refresh_interval} seconds.")
            
            # 更新动画的刷新间隔
            if hasattr(self, 'ani'):
                self.ani.event_source.interval = int(self.refresh_interval * 1000)
        except ValueError:
            print("Invalid refresh interval. Please enter a positive number.")
            self.refresh_var.set(self.refresh_interval)

    def start_data_thread(self):
        # Start a separate thread to read data periodically
        threading.Thread(target=self.update_data_thread, daemon=True).start()

    def display_error(self, message):
        # 可以使用 tk.messagebox 显示错误信息
        tk.messagebox.showerror("Error", message)

    def update_data_thread(self):
        while self.running:
            if self.csv_file and os.path.isfile(self.csv_file):
                try:
                    new_data = pd.read_csv(self.csv_file)
                    with self.data_lock:
                        self.data = new_data
                except Exception as e:
                    self.display_error(f"Error reading CSV file: {e}")
            else:
                self.display_error(f"File {self.csv_file} does not exist.")
            time.sleep(self.refresh_interval)

    def animate_plot(self, *args):
        # Start the animation
        self.ani = animation.FuncAnimation(
            self.fig,
            self.update_plot,
            interval=int(self.refresh_interval * 1000),
            cache_frame_data=False
        )
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def update_plot(self, frame):
        # Get selected images
        selected_indices = self.image_listbox.curselection()
        self.selected_images = [self.image_listbox.get(i) for i in selected_indices]

        if not self.selected_images:
            self.ax.clear()
            self.ax.set_title("No images selected")
            self.canvas.draw()
            return

        with self.data_lock:
            data_copy = self.data.copy()

        # Check if the metric exists in the data
        if self.metric not in data_copy.columns:
            self.ax.clear()
            self.ax.set_title(f"Metric '{self.metric}' not found in data")
            self.canvas.draw()
            return

        # Plot data for each selected image
        self.ax.clear()
        for img_name in self.selected_images:
            img_data = data_copy[data_copy['image_name'] == img_name]
            y_values = img_data[self.metric].values
            x_values = range(len(y_values))
            self.ax.plot(x_values, y_values, label=img_name)

        self.ax.set_xlabel('Iteration')
        self.ax.set_ylabel(self.metric)
        self.ax.set_title(f"Real-Time Plot of {self.metric}")
        self.ax.legend()
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def on_closing(self):
        # Handle closing of the application
        self.running = False
        plt.close('all')
        self.root.destroy()

def main():
    parser = argparse.ArgumentParser(description="VizDataRT")
    parser.add_argument(
        "csv_file",
        type=str,
        default=None,
        help="Path to the CSV file containing the data."
    )
    parser.add_argument(
        "--refresh-interval",
        type=float,
        default=0.5,
        help="Data refresh interval in seconds (default: 0.5)"
    )
    args = parser.parse_args()

    plotter = VizDataRT(csv_file=args.csv_file, refresh_interval=args.refresh_interval)

if __name__ == "__main__":
    main()
