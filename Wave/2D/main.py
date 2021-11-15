import sys

sys.path.append(".")
from network import DNN
import numpy as np
import torch
from torch.autograd import Variable, grad
from pyDOE import lhs

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# Parameters
x_min = 0.0
x_max = 1.0
y_min = 0.0
y_max = 1.0
t_min = 0.0
t_max = 2.0

N_ic = 500
N_bc = 200
N_f = 20000


########
x_points = lambda n: np.random.uniform(x_min, x_max, (n, 1))
y_points = lambda n: np.random.uniform(y_min, y_max, (n, 1))
t_points = lambda n: np.random.uniform(t_min, t_max, (n, 1))

# IC
x_ic = x_points(N_ic)
y_ic = y_points(N_ic)
t_ic = np.zeros((N_ic, 1))
xyt_ic = np.hstack([x_ic, y_ic, t_ic])

u_ic = np.sin(2 * np.pi * x_ic) * np.sin(np.pi * y_ic)
u_t_ic = np.zeros((N_ic, 1))
# u_t_ic = np.sin(x_ic * 2 * np.pi)


## BC
x_bc1 = np.zeros((N_bc, 1))
y_bc1 = y_points(N_bc)
t_bc1 = t_points(N_bc)
u_bc1 = np.zeros((N_bc, 1))

x_bc2 = np.ones((N_bc, 1)) * x_max
y_bc2 = y_points(N_bc)
t_bc2 = t_points(N_bc)
u_bc2 = np.zeros((N_bc, 1))

x_bc3 = x_points(N_bc)
y_bc3 = np.zeros((N_bc, 1))
t_bc3 = t_points(N_bc)
u_bc3 = np.zeros((N_bc, 1))

x_bc4 = x_points(N_bc)
y_bc4 = np.ones((N_bc, 1)) * y_max
t_bc4 = t_points(N_bc)
u_bc4 = np.zeros((N_bc, 1))

x_bc_x = np.vstack([x_bc1, x_bc2])
y_bc_x = np.vstack([y_bc1, y_bc2])
t_bc_x = np.vstack([t_bc1, t_bc2])
xyt_bc_x = np.hstack([x_bc_x, y_bc_x, t_bc_x])
u_bc_x = np.vstack([u_bc1, u_bc2])

x_bc_y = np.vstack([x_bc3, x_bc4])
y_bc_y = np.vstack([y_bc3, y_bc4])
t_bc_y = np.vstack([t_bc3, t_bc4])
xyt_bc_y = np.hstack([x_bc_y, y_bc_y, t_bc_y])
u_bc_y = np.vstack([u_bc3, u_bc4])


# collocation points
x_f = x_min + (x_max - x_min) * lhs(1, N_f)
y_f = y_min + (y_max - y_min) * lhs(1, N_f)
t_f = t_min + (t_max - t_min) * lhs(1, N_f)
xyt_f = np.hstack([x_f, y_f, t_f])
xyt_f = np.vstack([xyt_f, xyt_bc_x, xyt_bc_y, xyt_ic])

xyt_ic = torch.tensor(xyt_ic, dtype=torch.float32).to(device)
u_ic = torch.tensor(u_ic, dtype=torch.float32).to(device)
u_t_ic = torch.tensor(u_t_ic, dtype=torch.float32).to(device)
xyt_bc_x = torch.tensor(xyt_bc_x, dtype=torch.float32).to(device)
xyt_bc_y = torch.tensor(xyt_bc_y, dtype=torch.float32).to(device)
u_bc_x = torch.tensor(u_bc_x, dtype=torch.float32).to(device)
u_bc_y = torch.tensor(u_bc_y, dtype=torch.float32).to(device)
xyt_f = torch.tensor(xyt_f, dtype=torch.float32).to(device)


class PINN:
    c = 1

    def __init__(self) -> None:
        self.net = DNN(
            dim_in=3, dim_out=1, n_layer=6, n_node=20, activation=torch.nn.Tanh()
        ).to(device)
        self.iter = 0
        self.optimizer = torch.optim.LBFGS(
            self.net.parameters(),
            lr=1.0,
            max_iter=50000,
            max_eval=50000,
            history_size=50,
            tolerance_grad=1e-5,
            tolerance_change=1e-9,
            line_search_fn="strong_wolfe",
        )

    def ic(self, xyt):
        x = xyt[:, 0:1]
        y = xyt[:, 1:2]
        t = Variable(xyt[:, 2:3], requires_grad=True)
        u = self.net(torch.hstack([x, y, t]))
        u_t = grad(u.sum(), t, create_graph=True)[0]
        return u, u_t

    def bc_x(self, xyt):
        x = Variable(xyt[:, 0:1], requires_grad=True)
        y = xyt[:, 1:2]
        t = xyt[:, 2:3]
        u = self.net(torch.hstack([x, y, t]))
        u_x = grad(u.sum(), x, create_graph=True)[0]
        return u, u_x

    def bc_y(self, xyt):
        x = xyt[:, 0:1]
        y = Variable(xyt[:, 1:2], requires_grad=True)
        t = xyt[:, 2:3]
        u = self.net(torch.hstack([x, y, t]))
        u_y = grad(u.sum(), y, create_graph=True)[0]
        return u, u_y

    def f(self, xyt):
        x = Variable(xyt[:, 0:1], requires_grad=True)
        y = Variable(xyt[:, 1:2], requires_grad=True)
        t = Variable(xyt[:, 2:3], requires_grad=True)
        u = self.net(torch.hstack([x, y, t]))

        u_x = grad(u.sum(), x, create_graph=True)[0]
        u_xx = grad(u_x.sum(), x, create_graph=True)[0]

        u_y = grad(u.sum(), y, create_graph=True)[0]
        u_yy = grad(u_y.sum(), y, create_graph=True)[0]

        u_t = grad(u.sum(), t, create_graph=True)[0]
        u_tt = grad(u_t.sum(), t, create_graph=True)[0]

        f = u_tt - (self.c ** 2) * (u_xx + u_yy)
        return f

    def closure(self):
        self.optimizer.zero_grad()

        u_ic_pred, u_t_ic_pred = self.ic(xyt_ic)
        mse_u_ic = torch.mean(torch.square(u_ic_pred - u_ic))
        mse_u_t_ic = torch.mean(torch.square(u_t_ic_pred - u_t_ic))
        mse_ic = mse_u_ic
        # mse_ic += mse_u_t_ic

        # _, u_x_bc_pred = self.bc_x(xyt_bc_x)
        # _, u_y_bc_pred = self.bc_y(xyt_bc_y)
        u_bc_pred_x, _ = self.bc_x(xyt_bc_y)
        u_bc_pred_y, _ = self.bc_y(xyt_bc_y)
        mse_bc = torch.mean(torch.square(u_bc_pred_x - u_bc_x))
        mse_bc += torch.mean(torch.square(u_bc_pred_y - u_bc_y))

        f_pred = self.f(xyt_f)
        mse_f = torch.mean(torch.square(f_pred))
        loss = mse_ic + mse_bc + mse_f

        loss.backward()
        self.iter += 1
        print(
            f"\r{self.iter}, Loss : {loss.item():.5e}, ic : {mse_ic.item():.3e}, bc : {mse_bc.item():.3e}, f : {mse_f.item():.3e},",
            end="",
        )
        if self.iter % 500 == 0:
            print("")

        return loss


if __name__ == "__main__":
    pinn = PINN()
    pinn.optimizer.step(pinn.closure)
    torch.save(pinn.net.state_dict(), "./Wave/2D/weight.pt")
