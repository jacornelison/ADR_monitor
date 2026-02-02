# -*- coding: utf-8 -*-
"""
Created on Mon Dec 16 12:36:21 2024

@author: detector-group
"""
#%% Imports
import pyvisa as pv
import numpy as np
import time
import os
import matplotlib.pyplot as plt
import scraps as scr
import pickle as pk
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372_Channel
from scipy.interpolate import UnivariateSpline
import amp_control as ap
import vna_control as vn

#%%

def rebin_log(freq, data, nbins):
    """
    Adapted from Karia's code
    freq: np.array
        Frequency list to be rebinned
    data: np.array
        Data to be rebinned
    nbins: float
        number of bins after rebinning
    returns:
        center frequency of new bins, rebinned data, std of data within the bin
    """
    f_min = np.min(freq)
    f_max = np.max(freq)
    edges = np.logspace(np.log10(f_min), np.log10(f_max), num=nbins)
    avg_data = np.zeros(len(edges)-1)
    std_data = np.zeros(len(edges)-1)
    for j in range(len(edges)-1):
        lower_edge = edges[j]
        upper_edge = edges[j+1]
        #get indices of bin edges
        lower_index=np.argmin(np.abs(freq-lower_edge))
        upper_index=np.argmin(np.abs(freq-upper_edge))
        #compute bin values
        avg_data[j] = np.mean(data[lower_index:upper_index])
        std_data[j] = np.std(data[lower_index:upper_index])
    centerposts = np.logspace(np.log10(f_min), np.log10(f_max), num=2*nbins-1)
    center_freq = np.array([centerposts[2*i+1] for i in range(int(len(centerposts)/2))])
    indices = np.where(avg_data>0)
    return center_freq[indices], avg_data[indices], std_data[indices]

def calculate_spectrum(freq, I, Q, res_f, noise_I, noise_Q, sample_rate=200e3):
    """
    freq: np.array or list of float numbers
        The frequency list for the IQ sweep
    I: np.array or list of float numbers
        The I sweep data
    Q: np.array or list of float numbers
        The Q sweep data
    res_f: float
        The resonance frequency
    noise_I: np.array or list of float numbers
        The I timestream noise 
    noise_Q: np.array or list of float numbers
        The Q timestream noise
    sample_rate: float
        The sampling rate, float
    returns: np.array, np.array
        Frequency and power spectrum in unit of 1/Hz
    """
    # Based on Pete's thesis Eq. 4.5
    # length of data
    ts_len = len(noise_I) 
    # spline fit to the IQ vs. freq for calculating the derivative
    # for our adc, sometimes the first data point has abnormal values
    # so we are starting from 1:
    fq = UnivariateSpline(freq[1:], Q[1:], s=0.00001) 
    fi = UnivariateSpline(freq[1:], I[1:], s=0.00001)
    # derivative of Q relative to freq
    der_q = fq.derivative()(res_f) 
    der_i = fi.derivative()(res_f)
    # I and Q on resonance
    i_on_res = I[np.argmin(np.abs(freq-res_f))]
    q_on_res = Q[np.argmin(np.abs(freq-res_f))]
    # noise timestream, subtracting the on-resonance value
    noise_I = noise_I - i_on_res 
    noise_Q = noise_Q - q_on_res
    noise_I = np.array(noise_I)
    noise_Q = np.array(noise_Q)
    # Eq. 4.5, first line, df over f
    df_f = np.real((noise_I + 1j*noise_Q)/(der_i + 1j*der_q)/res_f)
    #df_f = poly(df_f, order=3)
    if len(df_f)>60000:
        filt_len = 1500
    else:
        filt_len = 15
    #df_f = filter_cosmic_df(df_f, filt_len=filt_len)

    f = np.fft.fftfreq(ts_len, d=1./sample_rate)
    norm_fac = 1 / sample_rate 
    
    hanning = np.hanning(len(df_f))
    mask_factor = np.mean(hanning**2)
    df_f = df_f * hanning
    
    spec = np.abs(np.fft.fft(df_f))**2 * 2.0 * norm_fac / ts_len / mask_factor
    return f[np.where(f>0)], spec[np.where(f>0)]   

#%% Noise measurements!



resnum = 1
FREQ = resListList[resnum][-1].freq
I = resListList[resnum][-1].I
Q = resListList[resnum][-1].Q
res_f = resListList[resnum][-1].lmfit_vals[1]
pwr = resListList[resnum][-1].pwr+40

vn.init_VNA_noise(res[resnum],1e4,1e5+1)
tstart = time.time()
vn.start_vna_sweep(pwr)
#%%
noise_I,noise_Q,noise_R,noise_THETA,noise_TIME = vn.get_VNA_data()
print(time.time()-tstart)

plt.figure(1,figsize=(10,6))
plt.plot(noise_I,noise_Q,'.')
plt.plot(I,Q)
plt.grid(True)
plt.show()



plt.figure(figsize=(10,5))
f, spec = calculate_spectrum(FREQ, I, Q, res_f, noise_I, noise_Q,sample_rate=1/np.median(np.diff(noise_TIME)))
#f,spec,std = rebin_log(f,spec,30)    
plt.loglog(f,spec)