import os
import copy
import numpy as np
import open3d as o3d

import kps


class Obj3d(object):
    def __init__(self, *args, **kwargs):
        self.load(*args, **kwargs)

    def load(
            self,
            filedir,
            scale_rate=0.01,
            scale_center=(0, 0, 0),
            sample_ld=1000,
            sample_hd=5000
    ):
        self.mesh = o3d.io.read_triangle_mesh(filedir).scale(scale_rate, center=scale_center)
        self.mesh.compute_vertex_normals()
        self.sampling(sample_ld, sample_hd)

    def sampling(self, sample_ld, sample_hd):
        self.pcd_ld = self.mesh.sample_points_poisson_disk(number_of_points=sample_ld, init_factor=5)
        self.pcd_hd = self.mesh.sample_points_poisson_disk(number_of_points=sample_hd, init_factor=5)

    def show(self):
        o3d.visualization.draw_geometries([
            self.mesh,
            copy.deepcopy(self.pcd_ld).translate((10, 0, 0)),
            copy.deepcopy(self.pcd_hd).translate((20, 0, 0)),
        ])

    def get_o3ds(self):
        objs = [
            copy.deepcopy(self.mesh),
            copy.deepcopy(self.pcd_ld).translate((10, 0, 0)),
            copy.deepcopy(self.pcd_hd).translate((20, 0, 0)),
        ]
        return objs


class Obj3d_Deform(Obj3d):
    def __init__(self, *args, **kwargs):
        Obj3d.__init__(self, *args, **kwargs)
        self.trans_rigid = None
        self.trans_nonrigid = None

    def set_trans_rigid(self, trans_rigid):
        self.trans_rigid = trans_rigid

    def set_trans_nonrigid(self, trans_nonrigid):
        self.trans_nonrigid = trans_nonrigid

    def offset_rotate(self):
        if self.trans_rigid is None:
            print("no rigid transformation")
            return

        rot = self.trans_rigid.rot
        center = pcd_get_center(self.pcd_hd)
        # center = (0, 0, 0)

        self.mesh.rotate(rot, center)
        self.pcd_hd.rotate(rot, center)
        self.pcd_ld.rotate(rot, center)

        print("reorientated 1 3d object")


class Obj3d_Kps(Obj3d_Deform):
    def __init__(self, *args, **kwargs):
        Obj3d_Deform.__init__(self, *args, **kwargs)
        self.kps = kps.Kps_Deform()
        self.kps_gt = kps.Kps()

    def select_kps_gt(self):
        self.kps_gt.select_kps_points()

    def set_trans_nonrigid(self, trans_nonrigid):
        Obj3d_Deform.set_trans_nonrigid(self, trans_nonrigid)
        self.kps.set_trans(self.trans_nonrigid)

    def cal_kps_deform(self):
        self.kps.setup_kps_deform()

    def diff_kps_pred_gt(self):
        return np.linalg.norm(
            self.kps.get_kps_source_points() - self.kps_gt.get_kps_source_points()
        )


def mesh2pcd(mesh, sample_d):
    return mesh.sample_points_poisson_disk(number_of_points=sample_d, init_factor=5)


def mesh_crop(mesh, min_bound=[-1000, -1000, -1000], max_bound=[1000, 1000, 1000]):
    bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound=min_bound, max_bound=max_bound)
    return mesh.crop(bbox)


def pcd2np(pcd):
    return np.asarray(pcd.points)


def np2pcd(points):
    """ Transform obj numpy cloud point to Open3D cloud point. """
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    return pcd


def pcd_crop(pcd, min_bound=[-1000, -1000, -1000], max_bound=[1000, 1000, 1000]):
    points = pcd2np(pcd)
    points_crop = []

    for point in points:
        min_to_point = point - min_bound
        point_to_max = max_bound - point
        less_than_zero = np.sum(min_to_point < 0) + np.sum(point_to_max < 0)
        if less_than_zero == 0:
            points_crop.append(point)

    return np2pcd(np.array(points_crop))


def pcd_crop_front(pcd, ratio=0.5):
    max_bound = pcd_get_max_bound(pcd)
    min_bound = pcd_get_min_bound(pcd)
    min_bound[2] = (1-ratio)*max_bound[2] + ratio*min_bound[2]
    return pcd_crop(pcd, min_bound)


def pcd_get_center(pcd):
    points = pcd2np(pcd)
    return np.mean(points, 0)


def pcd_get_max_bound(pcd):
    points = pcd2np(pcd)
    return np.ndarray.max(points, 0)


def pcd_get_min_bound(pcd):
    points = pcd2np(pcd)
    return np.ndarray.min(points, 0)


def search_nearest_point_idx(point, target_points):
    dist = np.linalg.norm(
        target_points - point, axis=1
    )
    idx = np.argmin(dist)
    return idx


def search_nearest_point(point, target_points):
    idx = search_nearest_point_idx(point, target_points)
    return target_points[idx]


def load_obj_series(
        folder,
        start=0,
        end=1,
        stride=1,
        obj_type=Obj3d_Kps,
        *args,
        **kwargs):
    """ load a series of point cloud obj files from a folder """
    files = os.listdir(folder)
    files = [folder + f for f in files if '.obj' in f]
    files.sort()

    o3_ls = []
    for n in range(start, end + 1, stride):
        filedir = files[n]
        o3_ls.append(obj_type(filedir=filedir, *args, **kwargs))
        print("loaded 1 mesh file: {}".format(filedir))

    return o3_ls


if __name__ == '__main__':
    o3 = Obj3d('dataset/45kmh_26markers_12fps/speed_45km_h_26_marker_set_1.000001.obj')

    o3_center = pcd_get_center(o3.pcd_ld)
    print("center: {}".format(o3_center))
    print("max bound: {}".format(pcd_get_max_bound(o3.pcd_ld)))
    print("min bound: {}".format(pcd_get_min_bound(o3.pcd_ld)))

    o3.show()
    o3d.visualization.draw_geometries([pcd_crop(o3.pcd_hd, min_bound=o3_center)])
    o3d.visualization.draw_geometries([mesh_crop(o3.mesh, min_bound=o3_center)])