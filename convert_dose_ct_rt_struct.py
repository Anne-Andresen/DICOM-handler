import glob
import os
import pydicom
import SimpleITK as sitk
import numpy as np

import shutil
from platipy.dicom.io import rtstruct_to_nifti
# Load the DICOM file


import SimpleITK as sitk
import os
import glob


def maybe_mkdir(path):
    if os.path.exists(path):
        pass
    else:
        os.mkdir(path)


def move_files(path):
    for filename in os.listdir(path):
        dst_path = os.path.join(path, 'CT')
        maybe_mkdir(dst_path)
        if filename.startswith('CT.'):
            src_file = os.path.join(path, filename)
            dst_file = os.path.join(dst_path, filename)
            shutil.move(src_file, dst_file)
def load_dicom_series(folder_path):
    # Load DICOM series from a folder
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(folder_path)
    reader.SetFileNames(dicom_names)
    return reader.Execute()




def register_images(fixed_image, moving_image):
    # Set up the registration
    registration_method = sitk.ImageRegistrationMethod()

    # Use mutual information as the metric for registration
    registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins=50)
    registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
    registration_method.SetMetricSamplingPercentage(0.01)

    # Set the optimizer parameters
    registration_method.SetOptimizerAsGradientDescent(learningRate=1.0, numberOfIterations=100, convergenceMinimumValue=1e-6, convergenceWindowSize=10)
    registration_method.SetOptimizerScalesFromPhysicalShift()

    # Set the interpolator
    registration_method.SetInterpolator(sitk.sitkLinear)

    # Execute the registration
    final_transform = registration_method.Execute(fixed_image, moving_image)

    # Resample the moving image using the obtained transform
    moving_resampled = sitk.Resample(moving_image, fixed_image, final_transform, sitk.sitkLinear, 0.0, moving_image.GetPixelID())

    return moving_resampled, final_transform





def overlay_and_save(ct_path, rtdose_path, output_folder, i):
    # Load CT and RTDose images
    ct_series = load_dicom_series(ct_path)
    rtdose_image = sitk.ReadImage(rtdose_path)

    # Ensure the pixel type is supported for registration
    ct_image = sitk.Cast(ct_series, sitk.sitkFloat32)
    rtdose_image = sitk.Cast(rtdose_image, sitk.sitkFloat32)
    '''
    # Get the DICOM metadata for the RTDose image
    rtdose_metadata = rtdose_image.GetMetaData()
    print('RTDose metadata keys:')
    for key in rtdose_metadata.keys():
        print(key)
    '''
    ds = pydicom.dcmread(rtdose_path)
    dgs = ds["DoseGridScaling"]
    vals = dgs.value
    #print('meta data: ', dgs.value)


    # Get the dose grid scaling value from the DICOM metadata
    dose_grid_scaling = vals
        #float(rtdose_metadata['0028,0302'].value)

    # Apply the dose grid scaling to the RTDose image
    rtdose_image = rtdose_image * dose_grid_scaling

    # Co-register RTDose to CT
    rtdose_registered, transform = register_images(ct_image, rtdose_image)

    # Resample RTDose to match CT size
    rtdose_resampled = sitk.Resample(rtdose_registered, ct_image)
    overlay_image = rtdose_resampled

    # Overlay the RTDose on the CT
    #overlay_image = sitk.Maximum(ct_image, rtdose_resampled)

    # Convert images to NIfTI format
    ct_nifti = sitk.GetArrayFromImage(ct_image)
    overlay_nifti = sitk.GetArrayFromImage(overlay_image)
    rs = glob.glob(os.path.dirname(rtdose_path) + '/RS.*')
    print('rs path: ', rs, output_folder)
    rt_struct = rs[0]
    save_path = os.path.join(output_folder, 'structs')
    maybe_mkdir(save_path)
    save_path = os.path.join(save_path, 'patient_' + str(i))
    maybe_mkdir(save_path)
    rtstruct_to_nifti.convert_rtstruct(ct_path,
                                       rt_struct,os.path.join(save_path, str(i) + '.nii.gz'))

    # Save CT and Overlay as NIfTI files
    Converted_CT = os.path.join(output_folder, 'CTs_nifti')
    maybe_mkdir(Converted_CT)
    converted_dose = os.path.join(output_folder, 'Dose_nifti')
    maybe_mkdir(converted_dose)
    ct_output_path = os.path.join(Converted_CT, str(i) + ".nii.gz")
    overlay_output_path = os.path.join(converted_dose, str(i) + ".nii.gz")

    sitk.WriteImage(ct_image, ct_output_path)
    sitk.WriteImage(overlay_image, overlay_output_path)



def run(data_path):
    patient_lst = glob.glob(data_path)
    CPR  = [os.path.basename(item) for item in patient_lst]
    patient_path = [os.path.join(os.path.dirname(data_path), cpr) for cpr in CPR]
    print('patient lst', patient_lst, 'cpr', CPR, 'patient paths', patient_path)
    i = 0

    for patient in patient_path:
        print('patient path', patient)
        lists = []
        ct_folder_path = os.path.join(patient,'CT')
        check = glob.glob(patient + '/CT*') # path to directory contianing the imaging files e.g. CTs 
        print('lelel', len(check))
        if len(check) != 0:
            print('Changing folder structure....')
            move_files(patient)
        #CTS_series = glob.glob(ct_folder_path)
        dose_path = patient
        dose_file = [lists.append(item) for item in glob.glob(os.path.join(dose_path, 'RD*'))] # find dose file
        print(dose_file, lists)
        #
        rtdose_folder_path = lists[0]
        output_folder_path = os.path.dirname(data_path)

        overlay_and_save(ct_folder_path, rtdose_folder_path, output_folder_path, i)
        i +=1


run(r'/*') # over all path to directories containg files
