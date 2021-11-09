import sys

sys.path.insert(0, "./Burgers")
import torch
from Burgers import PINN
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.gridspec import GridSpec
from scipy.io import loadmat

pgf_with_latex = {  # setup matplotlib to use latex for output
    "text.usetex": True,  # use LaTeX to write all text
    "font.family": "serif",
    "font.serif": [],  # blank entries should cause plots to inherit fonts from the document
    "font.sans-serif": [],
    "font.monospace": [],
    "axes.labelsize": 10,  # LaTeX default is 10pt font.
    "font.size": 10,
    "legend.fontsize": 8,  # Make the legend/label fonts a little smaller
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
}
plt.rcParams.update(pgf_with_latex)
np.random.seed(1234)
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


data = loadmat("./Burgers/burgers_shock.mat")
x = data["x"]
t = data["t"]
u = data["usol"]

x_, t_ = np.meshgrid(x, t)
x_ = x_.reshape(-1, 1)
t_ = t_.reshape(-1, 1)
u_ = u.reshape(-1, 1)

rand_idx = np.random.choice(len(u_), 2000, replace=False)
x_train = x_[rand_idx]
t_train = t_[rand_idx]

pinn = PINN(None)

with torch.no_grad():
    x_ts = torch.tensor(x_, dtype=torch.float64).to(device)
    t_ts = torch.tensor(t_, dtype=torch.float64).to(device)
    pinn.net.load_state_dict(torch.load("./Burgers/Burgers_identification/weight_0.pt"))
    u_pred = pinn.net(torch.hstack((x_ts, t_ts))).cpu().numpy().reshape((100, 256)).T

################ Plot ###################
fig = plt.figure(figsize=(16, 9.5))
gs0 = GridSpec(1, 2, figure=fig)
gs0.update(top=0.94, bottom=0.70, left=0.15, right=0.85, wspace=0)

ax = fig.add_subplot(gs0[0, :])
im = ax.imshow(
    u_pred,
    extent=[t_.min(), t_.max(), x_.min(), x_.max()],
    cmap="rainbow",
    aspect="auto",
    interpolation="nearest",
    origin="lower",
)

data_pt = ax.plot(
    t_train,
    x_train,
    "kx",
    label=f"Data ({len(t_train)}) points",
    markersize=4,
    clip_on=False,
    alpha=0.8,
)

divider = make_axes_locatable(ax)
cax = divider.append_axes("right", size="5%", pad=0.10)
cbar = fig.colorbar(im, cax=cax, label="$u(x,t)$")
cbar.ax.tick_params(labelsize=15)

ax.legend(
    loc="upper center",
    bbox_to_anchor=(0.9, -0.05),
    ncol=5,
    frameon=False,
    prop={"size": 15},
)
ax.set_xlabel("$t$")
ax.set_ylabel("$x$")
ax.set_title("$u(x,t)$")

gs1 = GridSpec(1, 3, figure=fig)
gs1.update(top=0.60, bottom=0.28, left=0.1, right=0.9, wspace=0.5)

t_slice = [0.25, 0.5, 0.75]
axes = []
for i in range(3):
    ax = fig.add_subplot(gs1[0, i])
    ax.plot(x, u[:, int(t_slice[i] * 100)], "b-", linewidth=2, label="Exact")
    ax.plot(x, u_pred[:, int(t_slice[i] * 100)], "r--", linewidth=2, label="Prediction")
    ax.set_xlabel("$x$")
    ax.set_ylabel("$u(x,t)$")
    ax.set_title(f"$t = {t_slice[i]}s$", fontsize=10)
    ax.axis("square")
    ax.set_xlim([-1.1, 1.1])
    ax.set_ylim([-1.1, 1.1])
    axes.append(ax)
axes[1].legend(
    loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False, fontsize=10
)

##############################################
gs2 = GridSpec(1, 1, figure=fig)
gs2.update(top=0.24, bottom=0, left=0.0, right=1.0, wspace=0.0)

ax = plt.subplot(gs2[:, :])
ax.axis("off")

l1 = pinn.net.state_dict()["lambda_1"].cpu().item()
l2 = np.exp(pinn.net.state_dict()["lambda_2"].cpu().item())
pinn.net.load_state_dict(torch.load("./Burgers/Burgers_identification/weight_1.pt"))
l1_noisy = pinn.net.state_dict()["lambda_1"].cpu().item()
l2_noisy = np.exp(pinn.net.state_dict()["lambda_2"].cpu().item())

s1 = r"$\begin{tabular}{ |c|c| }  \hline Correct PDE & $u_t + u u_x - 0.0031831 u_{xx} = 0$ \\  \hline Identified PDE (clean data) & "
s2 = r"$u_t + %.5f u u_x - %.7f u_{xx} = 0$ \\  \hline " % (l1, l2)
s3 = r"Identified PDE (1\% noise) & "
s4 = r"$u_t + %.5f u u_x - %.7f u_{xx} = 0$  \\  \hline " % (l1_noisy, l2_noisy)
s5 = r"\end{tabular}$"
s = s1 + s2 + s3 + s4 + s5
ax.text(0.21, 0.35, s, size=25)
fig.savefig(
    "./Burgers/Burgers_identification/Burgers_sol.png",
    bbox_inches="tight",
    pad_inches=0,
    dpi=500,
)
