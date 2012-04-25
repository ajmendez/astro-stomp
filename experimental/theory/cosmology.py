from scipy.interpolate import InterpolatedUnivariateSpline
from scipy import integrate
from scipy import special
import param  # cosmological parameter object from Cosmopy
import numpy

"""Classes for encoding basic cosmological parameters and quantities.

This is inspired by the CosmoPy package.  The intent is to have a singleton
object that contains all of the basic cosmological parameters as well as those
expected by the CAMB software.  In addition, we want a single class object
that can take those parameters and return standard cosmological quantities
(comoving distance, linear growth factor, etc.) as a function of redshift.
"""

__author__ = "Ryan Scranton <ryan.scranton@gmail.com>"


class SingleEpoch(object):
    """Container class for calculating cosmological values at a given redshift.

    Given a redshift and a set of parameters, SingleEpoch can return the
    comoving distance, angular diameter distance or luminosity distance for.
    Likewise, it can return a redshift, given an input comoving distance, as
    well as the growth factor D(z) and other cosmological parameters.
    """
    def __init__(self, redshift, camb_param=None, **kws):
        self._redshift = redshift

        if camb_param is None:
            camb_param = param.CambParams(**kws)

        self.omega_m0 = camb_param.omega_cdm + camb_param.omega_baryon
        self.omega_b0 = camb_param.omega_baryon
        self.omega_l0 = camb_param.omega_lambda
        self.h = camb_param.hubble/100.0
        self.H0 = 100.0/(3.0*10**5)
        self.omega_r0 = 4.17e-5/self.h**2
        self.sigma_8 = 0.811

        self.flat = True
        self.open = False
        self.closed = False

        omega_total = self.omega_m0 + self.omega_l0
        if omega_total <= 1.001 and omega_total >= 0.999:
            self.flat = True
        else:
            self.flat = False
        if omega_total <= 0.999:
            self.open = True
        else:
            self.open = False
        if omega_total > 1.001:
            self.closed = True
        else:
            self.closed = False

        self.k_min = 0.001
        self.k_max = 100.0
        self.n = camb_param.scalar_spectral_index[0]
        self.delta_H = (
            1.94e-5*self.omega_m0**(-0.785 - 0.05*numpy.log(self.omega_m0))*
            numpy.exp(-0.95*(self.n - 1) - 0.169*(self.n - 1)**2))

        self._initialize_defaults()

    def _initialize_defaults(self):
        self._chi, dist_err = integrate.quad(self.E, 0.0, self._redshift,
                                             limit=200)

        self.growth_norm, growth_norm_err = integrate.quad(
            self._growth_integrand, 0.0, 1.0,limit=200)
        self.growth_norm *= 2.5*self.omega_m0*numpy.sqrt(self.E0(0.0))

        a = 1.0/(1.0 + self._redshift)
        growth, growth_err = integrate.quad(self._growth_integrand, 0.0, a,
                                            limit=200)
        growth *= 2.5*self.omega_m0*numpy.sqrt(self.E0(self._redshift))
        self._growth = growth/self.growth_norm

        self.sigma_norm = 1.0
        self.sigma_norm = self.sigma_8*self._growth/self.sigma_r(8.0)

    def set_redshift(self, redshift):
        self._redshift = redshift

        self._initialize_defaults()

    def E(self, redshift):
        return 1.0/(self.H0*numpy.sqrt(self.E0(redshift)))

    def E0(self, redshift):
        a = 1.0/(1.0 + redshift)
        return self.omega_l0 + self.omega_m0/(a*a*a) + self.omega_r0/(a*a)

    def _growth_integrand(self, a):
        redshift = 1.0/a - 1.0
        return ((1.0 + redshift)/numpy.sqrt(self.E0(redshift)))**3

    def comoving_distance(self):
        return self._chi

    def luminosity_distance(self):
        return (1.0 + self._redshift)*self._chi

    def angular_diameter_distance(self):
        return self._chi/(1.0 + self._redshift)

    def redshift(self):
        return self._redshift

    def growth_factor(self):
        """Linear growth factor, normalized to unity at z = 0."""
        return self._growth

    def omega_m(self):
        return self.omega_m0*(1.0 + self._redshift)**3/self.E0(self._redshift)

    def omega_l(self):
        return self.omega_l0/self.E0(self._redshift)

    def delta_c(self):
        """Over-density threshold for linear, spherical collapse."""
        # Fitting function taken from NFW97
        delta_c = 0.15*(12.0*numpy.pi)**(2.0/3.0)
        if self.open:
            delta_c *= self.omega_m()**0.0185
        if self.flat and self.omega_m0 < 1.0001:
            delta_c *= self.omega_m()**0.0055

        return delta_c

    def delta_v(self):
        """Over-density for a collapsed, virialized halo."""
        # Fitting function taken from NFW97
        delta_v = 178.0
        if self.open:
            delta_v /= self.omega_m()**0.7
        if self.flat and self.omega_m0 < 1.0001:
            delta_v /= self.omega_m()**0.55

        return delta_v/self._growth

    def rho_crit(self):
        """Critical density in h^2 solar masses per cubic Mpc."""
        return 1.0e-29*1.0e-33*2.937999e+73*self.E0(self._redshift)
        #return (1.879e-29/(1.989e33)*numpy.power(3.086e24,3)*
        #        self.E0(self._redshift))

    def rho_bar(self):
        """Matter density in h^2 solar masses per cubic Mpc."""
        return self.rho_crit()*self.omega_m()

    # def _eh_transfer(self, k):
    #     """
    #     Eisenstein & Hu (1998) fitting function without BAO wiggles
    #     (see eqs. 26,28-31 in their paper)
    #     """

    #     theta = 2.728/2.7 # Temperature of CMB_2.7
    #     Ob = self.omega_b0
    #     Om = self.omega_m0
    #     h = self.h
    #     Omh2 = Om*h**2
        
    #     s = 44.5*numpy.log(9.83/Omh2)/numpy.sqrt(1.+10*(Ob*h**2)**(3/4))
    #     alpha = (1.-0.328*numpy.log(431.*Omh2)*Ob/Om +
    #              0.38*numpy.log(22.3*Omh2)*(Ob/Om)**2)
    #     Gamma = Om*h*(alpha + (1.-alpha)/(1.+(0.43*k*s)**4))
    #     q = k*theta/Gamma
        
    #     L0 = numpy.log(2*numpy.e+1.8*q)
    #     C0 = 14.2 + 731./(1.+62.5*q)
    #     T0 = L0/(L0 + C0*q**2)
    #     return T0

    def _eh_transfer(self, k):
        """
        Eisenstein & Hu (1998) fitting function without BAO wiggles
        (see eqs. 26,28-31 in their paper)
        """

        theta = 2.728/2.7 # Temperature of CMB_2.7
        Omh2 = self.omega_m0*self.h**2
        Omb2 = self.omega_b0*self.h**2
        omega_ratio = self.omega_b0/self.omega_m0
        s = 44.5*numpy.log(9.83/Omh2)/numpy.sqrt(1+10.0*(Omb2)**(3/4))
        alpha = (1 - 0.328*numpy.log(431.0*Omh2)*omega_ratio +
                 0.38*numpy.log(22.3*Omh2)*omega_ratio**2)
        Gamma_eff = self.omega_m0*self.h*(
            alpha + (1-alpha)/(1+0.43*k*s)**4)
        q = k*theta/Gamma_eff
        L0 = numpy.log(2*numpy.e + 1.8*q)
        C0 = 14.2 + 731.0/(1+62.5*q)
        return L0/(L0 + C0*q*q)

    def _eh_bao_transfer(self, k):
        """
        Eisenstein & Hu (1998) fitting function with BAO wiggles
        (see eqs. 26,28-31 in their paper)
        """
        theta = 2.728/2.7
        Ob = self.omega_b0
        Om = self.omega_m0
        Oc = Om-Ob
        O  = Om
        h = self.h
        Omh2 = Om*h**2
        Obh2 = Ob*h**2
        Oh2  = O*h**2
        ObO  = Ob/O
        
        zeq = 2.5e4*Oh2*theta**(-4)
        keq = 7.46e-2*Oh2*theta**(-2)
        b1  = 0.313*Oh2**(-0.419)*(1.+0.607*Oh2**0.674)
        b2  = 0.238*Oh2**0.223
        zd  = 1291.*(Oh2**0.251/(1.+0.659*Oh2**0.828))*(1.+b1*Obh2**b2)
        
        R = lambda z: 31.5*Obh2*theta**(-4)*(1000./z)
        Req = R(zeq)
        Rd  = R(zd)
        
        s = (2./(3.*keq))*numpy.sqrt(6./Req)*numpy.log((numpy.sqrt(1.+Rd)+numpy.sqrt(Rd+Req))/(1.+numpy.sqrt(Req)))
        ks = k*h*s
        
        kSilk = 1.6*Obh2**0.52*Oh2**0.73*(1.+(10.4*Oh2)**(-0.95))
        q = lambda k: k*h/(13.41*keq)
        
        G = lambda y: y*(-6.*numpy.sqrt(1.+y)+(2+3*y)*
                          numpy.log((numpy.sqrt(1.+y)+1.)/(numpy.sqrt(1.+y)-1.)))
        alpha_b = 2.07*keq*s*(1.+Rd)**(-3./4.)*G((1.+zeq)/(1.+zd))
        beta_b = 0.5 + (ObO) + (3.-2.*ObO)*numpy.sqrt((17.2*Oh2)**2+1.)
        
        C   = lambda x,a: (14.2/a) + 386./(1.+69.9*q(x)**1.08)
        T0t = lambda x,a,b: numpy.log(numpy.e+1.8*b*q(x))/(
            numpy.log(numpy.e+1.8*b*q(k))+C(x,a)*q(x)**2)
        
        a1 = (46.9*Oh2)**0.670*(1.+(32.1*Oh2)**(-0.532))
        a2 = (12.*Oh2)**0.424*(1.+(45.*Oh2)**(-0.582))
        alpha_c = a1**(-ObO)*a2**(-ObO**3)
        b1 = 0.944*(1.+(458.*Oh2)**(-0.708))**(-1)
        b2 = (0.395*Oh2)**(-0.0266)
        beta_c = 1./(1.+b1*((Oc/O)**b2-1))
        
        f = 1./(1.+(ks/5.4)**4)
        Tc = f*T0t(k,1,beta_c) + (1.-f)*T0t(k,alpha_c,beta_c)
        
        beta_node = 8.41*(Oh2**0.435)
        stilde = s/(1.+(beta_node/(ks))**3)**(1./3.)
        
        Tb1 = T0t(k,1.,1.)/(1.+(ks/5.2)**2)
        Tb2 = (alpha_b/(1.+(beta_b/ks)**3))*numpy.exp(-(k*h/kSilk)**1.4)
        Tb  = special.sph_jn(0,k*stilde)[0][0]*(Tb1+Tb2)
        return ObO*Tb + (Oc/O)*Tc

    def _bbks_Transfer(self, k):
        """BBKS transfer function."""
        Gamma = self.omega_m0*self.h
        #q = k/Gamma
        q = k/Gamma*numpy.exp(
            self.omega_b0 + numpy.sqrt(2*self.h)*self.omega_b0/self.omega_m0)
        return (numpy.log(1.0 + 2.34*q)/(2.34*q)*
                (1 + 3.89*q + (16.1*q)**2 + (5.47*q)**3 + (6.71*q)**4)**(-0.25))

    def delta_k(self, k):
        """k^3*P(k)/2*pi^2: dimensionless linear power spectrum."""
        delta_k = (
            self.delta_H**2*(k/self.H0)**(3 + self.n)*
            self._eh_transfer(k)**2)/self.h
        return delta_k*self._growth*self._growth*self.sigma_norm*self.sigma_norm

    def linear_power(self, k):
        return 2.0*numpy.pi*numpy.pi*self.delta_k(k)/(k*k*k)

    def sigma_r(self, scale):
        """RMS power on scale in Mpc/h"""
        if 1.0/scale <= self.k_min:
            self.k_min = (1.0/scale)/2.0
            print "WARNING: Requesting scale greater than k_min."
            print "\tResetting k_min to",self.k_min
        if 1.0/scale >= self.k_max:
            self.k_max = (1.0/scale)*2.0
            print "WARNING: Requesting scale greater than k_max."
            print "\tResetting k_max to",self.k_max
        sigma2, sigma2_err = integrate.quad(
            self._sigma_integrand, numpy.log(self.k_min),
            numpy.log(self.k_max), args=(scale,), limit=200)
        sigma2 /= numpy.pi*numpy.pi

        #sigma2 *= self._growth**2

        return numpy.sqrt(sigma2)

    def _sigma_integrand(self, ln_k, scale):
        k = numpy.exp(ln_k)
        dk = 1.0*k
        kR = scale*k

        W = 3.0*(
            numpy.sin(kR)/kR**3-numpy.cos(kR)/kR**2)

        return dk*self.linear_power(k)*W*W*k*k

    def sigma_m(self, mass):
        """RMS power on scale subtended by total mean mass in solar masses."""
        scale = (3.0*mass/(4.0*numpy.pi*self.rho_bar()))**(1.0/3.0)

        return self.sigma_r(scale)

    def sigma_r_prime(self, scale):
        pk2_int, pk2_error = integrate.quad(self._sigma_prime_integrand,
                                            numpy.log(self.k_min),
                                            numpy.log(self.k_max),args=(scale,),
                                            limit=200)
        return 1.0/(2*self.sigma_r(scale))*pk2_int*numpy*numpy.pi**2/2.0

    def sigma_m_prime(self, mass):
        scale = (3.0*mass/(4.0*numpy.pi*self.rho_bar()))**(1.0/3.0)
        d_M_d_R = 4.0*numpy.pi*self.rho_bar()*scale*scale

        return self.sigma_r_prime(scale)*d_M_d_R
    
    def _sigma_prime_integrand(self, ln_k, scale):
        k = numpy.exp(ln_k)
        dk = 1.0*k
        kR = scale*k
        
        W_1 = 18.0*(numpy.sin(kR)*(numpy.sin(kR)-kR*numpy.cos(kR)))/(
            kR*kR*kR*kR*scale)
        W_2 = 54.0*(numpy.sin(kR) - kR*numpy.cos(kR))**2/(
            kR*kR*kR*kR*kR*kR*scale)
        
        return (2*numpy.pi)**(-3.0)*dk*self.linear_power(k)*(W_1-W_2)*k*k

    def nu_r(self, scale):
        """Ratio of (delta_c/sigma(R))^2"""
        sqrt_nu = self.delta_c()/self.sigma_r(scale)
        return sqrt_nu*sqrt_nu

    def nu_m(self, mass):
        """Ratio of (delta_c/sigma(M))^2"""
        sqrt_nu = self.delta_c()/self.sigma_m(mass)
        return sqrt_nu*sqrt_nu

    def write(self, output_power_file_name=None):
        print "z = %1.4f" % self._redshift
        print "Comoving distance = %1.4f" % self._chi
        print "Growth factor = %1.4f" % self._growth
        print "Omega_m(z) = %1.4f" % self.omega_m()
        print "Omega_l(z) = %1.4f" % self.omega_l()
        print "Delta_V(z) = %1.4f" % self.delta_v()
        print "delta_c(z) = %1.4f" % self.delta_c()
        print "sigma_8(z) = %1.4f" % self.sigma_r(8.0)

        if not output_power_file_name is None:
            dln_k = (numpy.log(self.k_max) - numpy.log(self.k_min))/200
            ln_k_max = numpy.log(self.k_max) + dln_k
            ln_k_min = numpy.log(self.k_min) - dln_k

            f = open(output_power_file_name, "w")
            for ln_k in numpy.arange(ln_k_min, ln_k_max + dln_k, dln_k):
                k = numpy.exp(ln_k)
                f.write("%1.10f %1.10f\n" % (k, self.linear_power(k)))
            f.close()

class MultiEpoch(object):
    """Class for calculating cosmological values across a range of redshifts.

    Given an initial set of redshift bounds and a set of parameters, MultiEpoch
    can return the comoving distance, angular diameter distance or luminosity
    distance for any redshift over the input interval.  Likewise, it can return
    a redshift, given an input comoving distance, as well as the growth factor
    D(z) and a number of other cosmological parameters.
    """
    def __init__(self, z_min, z_max, camb_param=None, **kws):
        dz = (z_max - z_min)/100.0
        self.z_max = z_max + dz
        self.z_min = z_min - dz
        if self.z_min < 0.0: self.z_min = 0.0

        dz = (self.z_max - self.z_min)/100.0
        self._z_array = numpy.arange(self.z_min, self.z_max + dz, dz)
        self._chi_array = numpy.zeros_like(self._z_array)
        self._growth_array = numpy.zeros_like(self._z_array)

        if camb_param is None:
            camb_param = param.CambParams(**kws)

        self.epoch0 = SingleEpoch(0.0, camb_param)

        self.omega_m0 = self.epoch0.omega_m0
        self.omega_b0 = self.epoch0.omega_b0
        self.omega_l0 = self.epoch0.omega_l0
        self.h = self.epoch0.h
        self.H0 = self.epoch0.H0
        self.omega_r0 = self.epoch0.omega_r0

        self.flat = self.epoch0.flat
        self.open = self.epoch0.open
        self.closed = self.epoch0.closed

        self.k_min = self.epoch0.k_min
        self.k_max = self.epoch0.k_min
        self.n = self.epoch0.n
        self.delta_H = self.epoch0.delta_H

        self._initialize_splines()

    def _initialize_splines(self):
        for idx in xrange(self._z_array.size):
            dist, dist_err = integrate.quad(
                self.epoch0.E, 0.0, self._z_array[idx],limit=200)
            self._chi_array[idx] = dist
        self._chi_spline = InterpolatedUnivariateSpline(
            self._z_array, self._chi_array)
        self._z_spline = InterpolatedUnivariateSpline(
            self._chi_array, self._z_array)

        self.growth_norm = self.epoch0.growth_norm

        for idx in xrange(self._z_array.size):
            a = 1.0/(1.0 + self._z_array[idx])
            growth, growth_err = integrate.quad(
                self.epoch0._growth_integrand, 0.0, a,limit=200)
            growth *= 2.5*self.omega_m0*numpy.sqrt(
                self.epoch0.E0(self._z_array[idx]))
            self._growth_array[idx] = growth/self.growth_norm

        self._growth_spline = InterpolatedUnivariateSpline(
            self._z_array, self._growth_array)

    def E(self, redshift):
        return self.epoch0.E(redshift)

    def comoving_distance(self, redshift):
        distance = 0.0

        if redshift < self.z_max and redshift > self.z_min:
            distance = self._chi_spline(redshift)[0]
        else:
            print ("Warning: requested redshift outside of bounds!  "
                   "Returning 0.")

        return distance

    def luminosity_distance(self, redshift):
        return (1.0 + redshift)*self.comoving_distance(redshift)

    def angular_diameter_distance(self, redshift):
        return self.comoving_distance(redshift)/(1.0 + redshift)

    def redshift(self, comoving_distance):
        return self._z_spline(comoving_distance)[0]

    def growth_factor(self, redshift):
        """Linear growth factor, normalized to unity at z = 0."""
        growth = 1.0

        if redshift < self.z_max and redshift > self.z_min:
            growth = self._growth_spline(redshift)[0]
        else:
            print ("Warning: requested redshift outside of bounds!  "
                   "Returning unity.")

        return growth

    def omega_m(self, redshift=None):
        if redshift is None: redshift = 0.0
        return self.omega_m0*(1.0 + redshift)**3/self.epoch0.E0(redshift)

    def omega_l(self, redshift=None):
        if redshift is None: redshift = 0.0
        return self.omega_l0/self.epoch0.E0(redshift)

    def delta_c(self, redshift=None):
        """Over-density threshold for linear, spherical collapse."""
        # Fitting function taken from NFW97
        delta_c = 0.15*(12.0*numpy.pi)**(2.0/3.0)
        if self.open:
            delta_c *= self.omega_m(redshift)**0.0185
        if self.flat and self.omega_m0 < 1.0001:
            delta_c *= self.omega_m(redshift)**0.0055
        if redshift is None:
            return delta_c
        else:
            return delta_c/self.growth_factor(redshift)

    def delta_v(self, redshift=None):
        """Over-density for a collapsed, virialized halo."""
        # Fitting function taken from NFW97
        delta_v = 178.0
        if self.open:
            delta_v /= self.omega_m(redshift)**0.7
        if self.flat and self.omega_m0 < 1.0001:
            delta_v /= self.omega_m(redshift)**0.55
        if redshift is None:
            return delta_v
        else:
            return delta_v/self.growth_factor(redshift)

    def rho_crit(self, redshift=None):
        """Critical density in solar masses per cubic Mpc."""
        if redshift is None: redshift = 0.0
        return self.epoch0.E0(redshift)*1.0e-29*1.0e-33*2.937999e+73

    def rho_bar(self, redshift=None):
        """Matter density in solar masses per cubic Mpc."""
        return self.rho_crit(redshift)*self.omega_m(redshift)

    def delta_k(self, k, redshift=None):
        """k^2*P(k)/2*pi^2: dimensionless linear power spectrum.

        If redshift is omitted the results are given for z = 0.
        """
        delta_k = (
            self.delta_H**2*(3000.0*k/self.h)**(3 + self.n)*
            self.epoch0._bbks(k)**2)
        if not redshift is None:
            delta_k *= self.growth_factor(redshift)**2
        return delta_k

    def linear_power(self, k, redshift=None):
        return 2.0*numpy.pi*numpy.pi*self.delta_k(k*self.h, redshift)/(k*k*k)

    def sigma_r(self, scale, redshift=None):
        """RMS power on scale in Mpc/h"""
        sigma2, sigma2_err = integrate.quad(
            self.epoch0._sigma_integrand, numpy.log(self.k_min),
            numpy.log(self.k_max), args=(scale,),limit=200) # Limt was 50
        sigma2 /= numpy.pi*numpy.pi

        if not redshift is None:
            sigma2 *= self.growth_factor(redshift)**2

        return numpy.sqrt(sigma2)

    def sigma_m(self, mass, redshift=None):
        """RMS power on scale subtended by total mean mass in solar masses."""
        scale = (3.0*mass/(4.0*numpy.pi*self.rho_bar(redshift)))**(1.0/3.0)

        return self.sigma_r(scale, redshift)

    def nu_r(self, scale, redshift=None):
        """Ratio of (delta_c(z)/sigma(R, z))^2"""
        sqrt_nu = self.delta_c(redshift)/self.sigma_r(scale, redshift)
        return sqrt_nu*sqrt_nu

    def nu_m(self, mass, redshift=None):
        """Ratio of (delta_c(z)/sigma(M, z))^2"""
        sqrt_nu = self.delta_c(redshift)/self.sigma_m(mass, redshift)
        return sqrt_nu*sqrt_nu

    def write(self, output_file_name, output_power_file_name=None):
        f = open(output_file_name, "w")
        for z, chi, growth in zip(
            self._z_array, self._chi_array, self._growth_array):
            if z < self.z_max:
                f.write(
                    "%1.10f %1.10f %1.10f %1.10f "
                    "%1.10f %1.10f %1.10f %1.10f\n" % (
                    z, chi, growth, self.omega_m(z), self.omega_l(z),
                    self.delta_v(z), self.delta_c(z), self.sigma_r(8.0, z)))
        f.close()

        if not output_power_file_name is None:
            k_min = 0.001
            k_max = 100.0

            dln_k = (numpy.log(k_max) - numpy.log(k_min))/200
            ln_k_max = numpy.log(k_max) + dln_k
            ln_k_min = numpy.log(k_min) - dln_k

            ln_k_array = numpy.arange(ln_k_min, ln_k_max + dln_k, dln_k)
            f = open(output_power_file_name, "w")
            for ln_k in ln_k_array:
                k = numpy.exp(ln_k)
                f.write("%1.10f %1.10f\n" % (k, self.linear_power(k)))
            f.close()
