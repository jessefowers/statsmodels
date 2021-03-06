"""
Author: Terence L van Zyl
Modified: Kevin Sheppard
"""
import os
import warnings

import numpy as np
import pandas as pd
import scipy.stats
import pytest
from numpy.testing import assert_almost_equal, assert_allclose

from statsmodels.tools.sm_exceptions import EstimationWarning
from statsmodels.tsa.holtwinters import (ExponentialSmoothing,
                                         SimpleExpSmoothing, Holt, SMOOTHERS, PY_SMOOTHERS)

base, _ = os.path.split(os.path.abspath(__file__))
housing_data = pd.read_csv(os.path.join(base, 'results', 'housing-data.csv'))
housing_data = housing_data.set_index('DATE')
housing_data = housing_data.asfreq('MS')

SEASONALS = ('add', 'mul', None)
TRENDS = ('add', 'mul', None)


def _simple_dbl_exp_smoother(x, alpha, beta, l0, b0, nforecast=0):
    """
    Simple, slow, direct implementation of double exp smoothing for testing
    """
    n = x.shape[0]
    lvals = np.zeros(n)
    b = np.zeros(n)
    xhat = np.zeros(n)
    f = np.zeros(nforecast)
    lvals[0] = l0
    b[0] = b0
    # Special case the 0 observations since index -1 is not available
    xhat[0] = l0 + b0
    lvals[0] = alpha * x[0] + (1 - alpha) * (l0 + b0)
    b[0] = beta * (lvals[0] - l0) + (1 - beta) * b0
    for t in range(1, n):
        # Obs in index t is the time t forecast for t + 1
        lvals[t] = alpha * x[t] + (1 - alpha) * (lvals[t - 1] + b[t - 1])
        b[t] = beta * (lvals[t] - lvals[t - 1]) + (1 - beta) * b[t - 1]

    xhat[1:] = lvals[0:-1] + b[0:-1]
    f[:] = lvals[-1] + np.arange(1, nforecast + 1) * b[-1]
    err = x - xhat
    return lvals, b, f, err, xhat


class TestHoltWinters(object):
    @classmethod
    def setup_class(cls):
        # Changed for backwards compatibility with pandas

        # oildata_oil_json = '{"851990400000":446.6565229,"883526400000":454.4733065,"915062400000":455.662974,"946598400000":423.6322388,"978220800000":456.2713279,"1009756800000":440.5880501,"1041292800000":425.3325201,"1072828800000":485.1494479,"1104451200000":506.0481621,"1135987200000":526.7919833,"1167523200000":514.268889,"1199059200000":494.2110193}'
        # oildata_oil = pd.read_json(oildata_oil_json, typ='Series').sort_index()
        data = [446.65652290000003, 454.47330649999998, 455.66297400000002,
                423.63223879999998, 456.27132790000002, 440.58805009999998,
                425.33252010000001, 485.14944789999998, 506.04816210000001,
                526.79198329999997, 514.26888899999994, 494.21101929999998]
        index = ['1996-12-31 00:00:00', '1997-12-31 00:00:00', '1998-12-31 00:00:00',
                 '1999-12-31 00:00:00', '2000-12-31 00:00:00', '2001-12-31 00:00:00',
                 '2002-12-31 00:00:00', '2003-12-31 00:00:00', '2004-12-31 00:00:00',
                 '2005-12-31 00:00:00', '2006-12-31 00:00:00', '2007-12-31 00:00:00']
        oildata_oil = pd.Series(data, index)
        oildata_oil.index = pd.DatetimeIndex(oildata_oil.index,
                                             freq=pd.infer_freq(oildata_oil.index))
        cls.oildata_oil = oildata_oil

        # air_ausair_json = '{"662601600000":17.5534,"694137600000":21.8601,"725760000000":23.8866,"757296000000":26.9293,"788832000000":26.8885,"820368000000":28.8314,"851990400000":30.0751,"883526400000":30.9535,"915062400000":30.1857,"946598400000":31.5797,"978220800000":32.577569,"1009756800000":33.477398,"1041292800000":39.021581,"1072828800000":41.386432,"1104451200000":41.596552}'
        # air_ausair = pd.read_json(air_ausair_json, typ='Series').sort_index()
        data = [17.5534, 21.860099999999999, 23.886600000000001,
                26.929300000000001, 26.888500000000001, 28.831399999999999,
                30.075099999999999, 30.953499999999998, 30.185700000000001,
                31.579699999999999, 32.577568999999997, 33.477398000000001,
                39.021580999999998, 41.386431999999999, 41.596552000000003]
        index = ['1990-12-31 00:00:00', '1991-12-31 00:00:00', '1992-12-31 00:00:00',
                 '1993-12-31 00:00:00', '1994-12-31 00:00:00', '1995-12-31 00:00:00',
                 '1996-12-31 00:00:00', '1997-12-31 00:00:00', '1998-12-31 00:00:00',
                 '1999-12-31 00:00:00', '2000-12-31 00:00:00', '2001-12-31 00:00:00',
                 '2002-12-31 00:00:00', '2003-12-31 00:00:00', '2004-12-31 00:00:00']
        air_ausair = pd.Series(data, index)
        air_ausair.index = pd.DatetimeIndex(air_ausair.index,
                                            freq=pd.infer_freq(air_ausair.index))
        cls.air_ausair = air_ausair

        # livestock2_livestock_json = '{"31449600000":263.917747,"62985600000":268.307222,"94608000000":260.662556,"126144000000":266.639419,"157680000000":277.515778,"189216000000":283.834045,"220838400000":290.309028,"252374400000":292.474198,"283910400000":300.830694,"315446400000":309.286657,"347068800000":318.331081,"378604800000":329.37239,"410140800000":338.883998,"441676800000":339.244126,"473299200000":328.600632,"504835200000":314.255385,"536371200000":314.459695,"567907200000":321.413779,"599529600000":329.789292,"631065600000":346.385165,"662601600000":352.297882,"694137600000":348.370515,"725760000000":417.562922,"757296000000":417.12357,"788832000000":417.749459,"820368000000":412.233904,"851990400000":411.946817,"883526400000":394.697075,"915062400000":401.49927,"946598400000":408.270468,"978220800000":414.2428}'
        # livestock2_livestock = pd.read_json(livestock2_livestock_json, typ='Series').sort_index()
        data = [263.91774700000002, 268.30722200000002, 260.662556,
                266.63941899999998, 277.51577800000001, 283.834045,
                290.30902800000001, 292.474198, 300.83069399999999,
                309.28665699999999, 318.33108099999998, 329.37239,
                338.88399800000002, 339.24412599999999, 328.60063200000002,
                314.25538499999999, 314.45969500000001, 321.41377899999998,
                329.78929199999999, 346.38516499999997, 352.29788200000002,
                348.37051500000001, 417.56292200000001, 417.12356999999997,
                417.749459, 412.233904, 411.94681700000001, 394.69707499999998,
                401.49927000000002, 408.27046799999999, 414.24279999999999]
        index = ['1970-12-31 00:00:00', '1971-12-31 00:00:00', '1972-12-31 00:00:00',
                 '1973-12-31 00:00:00', '1974-12-31 00:00:00', '1975-12-31 00:00:00',
                 '1976-12-31 00:00:00', '1977-12-31 00:00:00', '1978-12-31 00:00:00',
                 '1979-12-31 00:00:00', '1980-12-31 00:00:00', '1981-12-31 00:00:00',
                 '1982-12-31 00:00:00', '1983-12-31 00:00:00', '1984-12-31 00:00:00',
                 '1985-12-31 00:00:00', '1986-12-31 00:00:00', '1987-12-31 00:00:00',
                 '1988-12-31 00:00:00', '1989-12-31 00:00:00', '1990-12-31 00:00:00',
                 '1991-12-31 00:00:00', '1992-12-31 00:00:00', '1993-12-31 00:00:00',
                 '1994-12-31 00:00:00', '1995-12-31 00:00:00', '1996-12-31 00:00:00',
                 '1997-12-31 00:00:00', '1998-12-31 00:00:00', '1999-12-31 00:00:00',
                 '2000-12-31 00:00:00']
        livestock2_livestock = pd.Series(data, index)
        livestock2_livestock.index = pd.DatetimeIndex(
            livestock2_livestock.index,
            freq=pd.infer_freq(livestock2_livestock.index))
        cls.livestock2_livestock = livestock2_livestock

        # aust_json = '{"1104537600000":41.727458,"1112313600000":24.04185,"1120176000000":32.328103,"1128124800000":37.328708,"1136073600000":46.213153,"1143849600000":29.346326,"1151712000000":36.48291,"1159660800000":42.977719,"1167609600000":48.901525,"1175385600000":31.180221,"1183248000000":37.717881,"1191196800000":40.420211,"1199145600000":51.206863,"1207008000000":31.887228,"1214870400000":40.978263,"1222819200000":43.772491,"1230768000000":55.558567,"1238544000000":33.850915,"1246406400000":42.076383,"1254355200000":45.642292,"1262304000000":59.76678,"1270080000000":35.191877,"1277942400000":44.319737,"1285891200000":47.913736}'
        # aust = pd.read_json(aust_json, typ='Series').sort_index()
        data = [41.727457999999999, 24.04185, 32.328102999999999,
                37.328707999999999, 46.213152999999998, 29.346326000000001,
                36.482909999999997, 42.977719, 48.901524999999999,
                31.180221, 37.717880999999998, 40.420211000000002,
                51.206862999999998, 31.887228, 40.978262999999998,
                43.772491000000002, 55.558566999999996, 33.850915000000001,
                42.076383, 45.642291999999998, 59.766779999999997,
                35.191876999999998, 44.319737000000003, 47.913736]
        index = ['2005-03-01 00:00:00', '2005-06-01 00:00:00', '2005-09-01 00:00:00',
                 '2005-12-01 00:00:00', '2006-03-01 00:00:00', '2006-06-01 00:00:00',
                 '2006-09-01 00:00:00', '2006-12-01 00:00:00', '2007-03-01 00:00:00',
                 '2007-06-01 00:00:00', '2007-09-01 00:00:00', '2007-12-01 00:00:00',
                 '2008-03-01 00:00:00', '2008-06-01 00:00:00', '2008-09-01 00:00:00',
                 '2008-12-01 00:00:00', '2009-03-01 00:00:00', '2009-06-01 00:00:00',
                 '2009-09-01 00:00:00', '2009-12-01 00:00:00', '2010-03-01 00:00:00',
                 '2010-06-01 00:00:00', '2010-09-01 00:00:00', '2010-12-01 00:00:00']
        aust = pd.Series(data, index)
        aust.index = pd.DatetimeIndex(aust.index,
                                      freq=pd.infer_freq(aust.index))
        cls.aust = aust


    def test_predict(self):
        fit1 = ExponentialSmoothing(self.aust, seasonal_periods=4, trend='add',
                                    seasonal='mul').fit()
        fit2 = ExponentialSmoothing(self.aust, seasonal_periods=4, trend='add',
                                    seasonal='mul').fit()
        # fit3 = ExponentialSmoothing(self.aust, seasonal_periods=4, trend='add',
        # seasonal='mul').fit(remove_bias=True, use_basinhopping=True)
        assert_almost_equal(fit1.predict('2011-03-01 00:00:00',
                                         '2011-12-01 00:00:00'),
                            [61.3083, 37.3730, 46.9652, 51.5578], 3)
        assert_almost_equal(fit2.predict(end='2011-12-01 00:00:00'),
                            [61.3083, 37.3730, 46.9652, 51.5578], 3)

    # assert_almost_equal(fit3.predict('2010-10-01 00:00:00', '2010-10-01 00:00:00'), [49.087], 3)

    def test_ndarray(self):
        fit1 = ExponentialSmoothing(self.aust.values, seasonal_periods=4,
                                    trend='add', seasonal='mul').fit()
        assert_almost_equal(fit1.forecast(4),
                            [61.3083, 37.3730, 46.9652, 51.5578], 3)

    # FIXME: this is passing 2019-05-22 on some platforms; what has changed?
    @pytest.mark.xfail(reason='Optimizer does not converge', strict=False)
    def test_forecast(self):
        fit1 = ExponentialSmoothing(self.aust, seasonal_periods=4, trend='add',
                                    seasonal='add').fit()
        assert_almost_equal(fit1.forecast(steps=4),
                            [60.9542, 36.8505, 46.1628, 50.1272], 3)

    def test_simple_exp_smoothing(self):
        fit1 = SimpleExpSmoothing(self.oildata_oil).fit(0.2, optimized=False)
        fit2 = SimpleExpSmoothing(self.oildata_oil).fit(0.6, optimized=False)
        fit3 = SimpleExpSmoothing(self.oildata_oil).fit()
        assert_almost_equal(fit1.forecast(1), [484.802468], 4)
        assert_almost_equal(fit1.level,
                            [446.65652290, 448.21987962, 449.7084985,
                             444.49324656, 446.84886283, 445.59670028,
                             441.54386424, 450.26498098, 461.4216172,
                             474.49569042, 482.45033014, 484.80246797], 4)
        assert_almost_equal(fit2.forecast(1), [501.837461], 4)
        assert_almost_equal(fit3.forecast(1), [496.493543], 4)
        assert_almost_equal(fit3.params['smoothing_level'], 0.891998, 4)
        # has to be 3 for old python2.7 scipy versions
        assert_almost_equal(fit3.params['initial_level'], 447.478440, 3)

    def test_holt(self):
        fit1 = Holt(self.air_ausair).fit(smoothing_level=0.8,
                                         smoothing_slope=0.2, optimized=False)
        fit2 = Holt(self.air_ausair, exponential=True).fit(
            smoothing_level=0.8, smoothing_slope=0.2,
            optimized=False)
        fit3 = Holt(self.air_ausair, damped=True).fit(smoothing_level=0.8,
                                                      smoothing_slope=0.2)
        assert_almost_equal(fit1.forecast(5), [43.76, 45.59, 47.43, 49.27, 51.10], 2)
        assert_almost_equal(fit1.slope,
                            [3.617628, 3.59006512, 3.33438212, 3.23657639, 2.69263502,
                             2.46388914, 2.2229097, 1.95959226, 1.47054601, 1.3604894,
                             1.28045881, 1.20355193, 1.88267152, 2.09564416, 1.83655482], 4)
        assert_almost_equal(fit1.fittedfcast,
                            [21.8601, 22.032368, 25.48461872, 27.54058587,
                             30.28813356, 30.26106173, 31.58122149, 32.599234,
                             33.24223906, 32.26755382, 33.07776017, 33.95806605,
                             34.77708354, 40.05535303, 43.21586036, 43.75696849], 4)
        assert_almost_equal(fit2.forecast(5),
                            [44.60, 47.24, 50.04, 53.01, 56.15], 2)
        assert_almost_equal(fit3.forecast(5),
                            [42.85, 43.81, 44.66, 45.41, 46.06], 2)

    @pytest.mark.smoke
    def test_holt_damp_fit(self):
        # Smoke test for parameter estimation
        fit1 = SimpleExpSmoothing(self.livestock2_livestock).fit()
        mod4 = Holt(self.livestock2_livestock, damped=True)
        fit4 = mod4.fit(damping_slope=0.98)
        mod5 = Holt(self.livestock2_livestock, exponential=True, damped=True)
        fit5 = mod5.fit()
        # We accept the below values as we getting a better SSE than text book
        assert_almost_equal(fit1.params['smoothing_level'], 1.00, 2)
        assert_almost_equal(fit1.params['smoothing_slope'], np.NaN, 2)
        assert_almost_equal(fit1.params['damping_slope'], np.NaN, 2)
        assert_almost_equal(fit1.params['initial_level'], 263.92, 2)
        assert_almost_equal(fit1.params['initial_slope'], np.NaN, 2)
        assert_almost_equal(fit1.sse, 6761.35, 2)  # 6080.26

        assert_almost_equal(fit4.params['smoothing_level'], 0.98, 2)
        assert_almost_equal(fit4.params['smoothing_slope'], 0.00, 2)
        assert_almost_equal(fit4.params['damping_slope'], 0.98, 2)
        assert_almost_equal(fit4.params['initial_level'], 257.36, 2)
        assert_almost_equal(fit4.params['initial_slope'], 6.64, 2)
        assert_almost_equal(fit4.sse, 6036.56, 2)  # 6080.26

        assert_almost_equal(fit5.params['smoothing_level'], 0.97, 2)
        assert_almost_equal(fit5.params['smoothing_slope'], 0.00, 2)
        assert_almost_equal(fit5.params['damping_slope'], 0.98, 2)
        assert_almost_equal(fit5.params['initial_level'], 258.95, 2)
        assert_almost_equal(fit5.params['initial_slope'], 1.04, 2)
        assert_almost_equal(fit5.sse, 6082.00, 2)  # 6100.11

    def test_holt_damp_R(self):
        # Test the damping parameters against the R forecast packages `ets`
        # library(ets)
        # livestock2_livestock <- c(...)
        # res <- ets(livestock2_livestock, model='AAN', damped=TRUE, phi=0.98)
        mod = Holt(self.livestock2_livestock, damped=True)
        params = {
            'smoothing_level': 0.97402626,
            'smoothing_slope': 0.00010006,
            'damping_slope': 0.98,
            'initial_level': 252.59039965,
            'initial_slope': 6.90265918}
        fit = mod.fit(optimized=False, **params)

        # Check that we captured the parameters correctly
        for key in params.keys():
            assert_allclose(fit.params[key], params[key])

        # Summary output
        # print(res$mse)
        assert_allclose(fit.sse / mod.nobs, 195.4397924865488, atol=1e-3)
        # print(res$aicc)
        # TODO: this fails - different AICC definition?
        # assert_allclose(fit.aicc, 282.386426659408, atol=1e-3)
        # print(res$bic)
        # TODO: this fails - different BIC definition?
        # assert_allclose(fit.bic, 287.1563626818338)

        # print(res$states[,'l'])
        # note: this array includes the initial level
        desired = [
            252.5903996514365, 263.7992355246843, 268.3623324350207,
            261.0312983437606, 266.6590942700923, 277.3958197247272,
            283.8256217863908, 290.2962560621914, 292.5701438129583,
            300.7655919939834, 309.2118057241649, 318.2377698496536,
            329.2238709362550, 338.7709778307978, 339.3669793596703,
            329.0127022356033, 314.7684267018998, 314.5948077575944,
            321.3612035017972, 329.6924360833211, 346.0712138652086,
            352.2534120008911, 348.5862874190927, 415.8839400693967,
            417.2018843196238, 417.8435306633725, 412.4857261252961,
            412.0647865321129, 395.2500605270393, 401.4367438266322,
            408.1907701386275, 414.1814574903921]
        assert_allclose(np.r_[fit.params['initial_level'], fit.level], desired)

        # print(res$states[,'b'])
        # note: this array includes the initial slope
        desired = [
            6.902659175332394, 6.765062519124909, 6.629548973536494,
            6.495537532917715, 6.365550989616566, 6.238702070454378,
            6.113960476763530, 5.991730467006233, 5.871526257315264,
            5.754346516684953, 5.639547926790058, 5.527116419415724,
            5.417146212898857, 5.309238662451385, 5.202580636191761,
            5.096941655567694, 4.993026494493987, 4.892645486210410,
            4.794995106664251, 4.699468310763351, 4.606688340205792,
            4.514725879754355, 4.423600168391240, 4.341595902295941,
            4.254462303550087, 4.169010676686062, 4.084660399498803,
            4.002512751871354, 3.920332298146730, 3.842166514133902,
            3.765630194200260, 3.690553892582855]
        # TODO: not sure why the precision is so low here...
        assert_allclose(np.r_[fit.params['initial_slope'], fit.slope], desired,
                        atol=1e-3)

        # print(res$fitted)
        desired = [
            259.3550056432622, 270.4289967934267, 274.8592904290865,
            267.3969251260200, 272.8973342399166, 283.5097477537724,
            289.8173030536191, 296.1681519198575, 298.3242395451272,
            306.4048515803347, 314.7385626924191, 323.6543439406810,
            334.5326742248959, 343.9740317200002, 344.4655083831382,
            334.0077050580596, 319.6615926665040, 319.3896003340806,
            326.0602987063282, 334.2979150278692, 350.5857684386102,
            356.6778433630504, 352.9214155841161, 420.1387040536467,
            421.3712573771029, 421.9291611265248, 416.4886933168049,
            415.9872490289468, 399.0919861792231, 405.2020670104834,
            411.8810877289437]
        assert_allclose(fit.fittedvalues, desired, atol=1e-3)

        # print(forecast(res)$mean)
        desired = [
            417.7982003051233, 421.3426082635598, 424.8161280628277,
            428.2201774661102, 431.5561458813270, 434.8253949282395,
            438.0292589942138, 441.1690457788685, 444.2460368278302,
            447.2614880558126]
        assert_allclose(fit.forecast(10), desired, atol=1e-4)

    def test_hw_seasonal(self):
        mod = ExponentialSmoothing(self.aust, seasonal_periods=4,
                                   trend='additive', seasonal='additive')
        fit1 = mod.fit(use_boxcox=True)
        fit2 = ExponentialSmoothing(self.aust, seasonal_periods=4, trend='add',
                                    seasonal='mul').fit(use_boxcox=True)
        assert_almost_equal(fit1.forecast(8),
                            [61.34, 37.24, 46.84, 51.01, 64.47, 39.78, 49.64, 53.90],
                            2)
        assert_almost_equal(fit2.forecast(8),
                            [60.97, 36.99, 46.71, 51.48, 64.46, 39.02, 49.29, 54.32],
                            2)
        ExponentialSmoothing(self.aust, seasonal_periods=4, trend='mul',
                             seasonal='add').fit(use_boxcox='log')
        ExponentialSmoothing(self.aust,
                             seasonal_periods=4,
                             trend='multiplicative',
                             seasonal='multiplicative').fit(use_boxcox='log')
        # Skip since estimator is unstable
        # assert_almost_equal(fit5.forecast(1), [60.60], 2)
        # assert_almost_equal(fit6.forecast(1), [61.47], 2)

    # FIXME: this is passing 2019-05-22; what has changed?
    # @pytest.mark.xfail(reason='Optimizer does not converge')
    def test_hw_seasonal_buggy(self):
        fit3 = ExponentialSmoothing(self.aust, seasonal_periods=4,
                                    seasonal='add').fit(use_boxcox=True)
        assert_almost_equal(fit3.forecast(8),
                            [59.91, 35.71, 44.64, 47.62, 59.91, 35.71, 44.64, 47.62],
                            2)
        fit4 = ExponentialSmoothing(self.aust, seasonal_periods=4,
                                    seasonal='mul').fit(use_boxcox=True)
        assert_almost_equal(fit4.forecast(8),
                            [60.71, 35.70, 44.63, 47.55, 60.71, 35.70, 44.63, 47.55],
                            2)


@pytest.mark.parametrize('trend_seasonal', (('mul', None), (None, 'mul'), ('mul', 'mul')))
def test_negative_multipliative(trend_seasonal):
    trend, seasonal = trend_seasonal
    y = -np.ones(100)
    with pytest.raises(ValueError):
        ExponentialSmoothing(y, trend=trend, seasonal=seasonal, seasonal_periods=10)


@pytest.mark.parametrize('seasonal', SEASONALS)
def test_dampen_no_trend(seasonal):
    y = -np.ones(100)
    with pytest.raises(TypeError):
        ExponentialSmoothing(housing_data, trend=False, seasonal=seasonal, damped=True,
                             seasonal_periods=10)


@pytest.mark.parametrize('seasonal', ('add', 'mul'))
def test_invalid_seasonal(seasonal):
    y = pd.Series(-np.ones(100),index=pd.date_range('2000-1-1', periods=100, freq='MS'))
    with pytest.raises(ValueError):
        ExponentialSmoothing(y, seasonal=seasonal, seasonal_periods=1)


def test_2d_data():
    with pytest.raises(ValueError):
        ExponentialSmoothing(pd.concat([housing_data, housing_data], 1)).fit()


def test_infer_freq():
    hd2 = housing_data.copy()
    hd2.index = list(hd2.index)
    with warnings.catch_warnings(record=True) as w:
        mod = ExponentialSmoothing(hd2, trend='add', seasonal='add')
        assert len(w) == 1
        assert 'ValueWarning' in str(w[0])
    assert mod.seasonal_periods == 12


@pytest.mark.parametrize('trend', TRENDS)
@pytest.mark.parametrize('seasonal', SEASONALS)
def test_start_params(trend, seasonal):
    mod = ExponentialSmoothing(housing_data, trend='add', seasonal='add')
    res = mod.fit()
    res2 = mod.fit(start_params=res.mle_retvals.x)
    assert res2.sse <= res.sse


def test_no_params_to_optimize():
    mod = ExponentialSmoothing(housing_data)
    with pytest.warns(EstimationWarning):
        mod.fit(smoothing_level=0.5, initial_level=housing_data.iloc[0])


def test_invalid_start_param_length():
    mod = ExponentialSmoothing(housing_data)
    with pytest.raises(ValueError):
        mod.fit(start_params=np.array([0.5]))


def test_basin_hopping(reset_randomstate):
    mod = ExponentialSmoothing(housing_data, trend='add')
    res = mod.fit()
    res2 = mod.fit(use_basinhopping=True)
    # Basin hopping occasionally prduces a slightly larger objective
    tol = 1e-5
    assert res2.sse <= res.sse + tol


def test_debiased():
    mod = ExponentialSmoothing(housing_data, trend='add')
    res = mod.fit()
    res2 = mod.fit(remove_bias=True)
    assert np.any(res.fittedvalues != res2.fittedvalues)


@pytest.mark.smoke
@pytest.mark.parametrize('trend', TRENDS)
@pytest.mark.parametrize('seasonal', SEASONALS)
def test_float_boxcox(trend, seasonal):
    res = ExponentialSmoothing(housing_data, trend=trend, seasonal=seasonal).fit(use_boxcox=0.5)
    assert_allclose(res.params['use_boxcox'], 0.5)


@pytest.mark.parametrize('trend', TRENDS)
@pytest.mark.parametrize('seasonal', SEASONALS)
def test_equivalence_cython_python(trend, seasonal):
    mod = ExponentialSmoothing(housing_data, trend=trend, seasonal=seasonal)

    with pytest.warns(None):
        # Overflow in mul-mul case fixed
        res = mod.fit()

    res.summary()  # Smoke test
    params = res.params
    nobs = housing_data.shape[0]
    y = np.squeeze(np.asarray(housing_data))
    m = 12 if seasonal else 0
    lvals = np.zeros(nobs)
    b = np.zeros(nobs)
    s = np.zeros(nobs + m - 1)
    p = np.zeros(6 + m)
    max_seen = np.finfo(np.double).max
    alpha = params['smoothing_level']
    beta = params['smoothing_slope']
    gamma = params['smoothing_seasonal']
    phi = params['damping_slope']
    phi = 1.0 if np.isnan(phi) else phi
    l0 = params['initial_level']
    b0 = params['initial_slope']
    p[:6] = alpha, beta, gamma, l0, b0, phi
    if seasonal:
        p[6:] = params['initial_seasons']
    xi = np.ones_like(p).astype(np.uint8)
    py_func = PY_SMOOTHERS[(seasonal, trend)]
    cy_func = SMOOTHERS[(seasonal, trend)]
    p_copy = p.copy()
    sse_cy = cy_func(p, xi, p_copy, y, lvals, b, s, m, nobs, max_seen)
    sse_py = py_func(p, xi, p_copy, y, lvals, b, s, m, nobs, max_seen)
    assert_allclose(sse_py, sse_cy)


def test_direct_holt_add():
    mod = SimpleExpSmoothing(housing_data)
    res = mod.fit()
    x = np.squeeze(np.asarray(mod.endog))
    alpha = res.params['smoothing_level']
    l, b, f, err, xhat = _simple_dbl_exp_smoother(x, alpha, beta=0.0,
                                                  l0=res.params['initial_level'], b0=0.0,
                                                  nforecast=5)

    assert_allclose(l, res.level)
    assert_allclose(f, res.level.iloc[-1] * np.ones(5))
    assert_allclose(f, res.forecast(5))

    mod = ExponentialSmoothing(housing_data, trend='add')
    res = mod.fit()
    x = np.squeeze(np.asarray(mod.endog))
    alpha = res.params['smoothing_level']
    beta = res.params['smoothing_slope']
    l, b, f, err, xhat = _simple_dbl_exp_smoother(x, alpha, beta=beta,
                                                  l0=res.params['initial_level'],
                                                  b0=res.params['initial_slope'], nforecast=5)

    assert_allclose(xhat, res.fittedvalues)
    assert_allclose(l + b, res.level + res.slope)
    assert_allclose(l, res.level)
    assert_allclose(b, res.slope)
    assert_allclose(f, res.level.iloc[-1] + res.slope.iloc[-1] * np.array([1, 2, 3, 4, 5]))
    assert_allclose(f, res.forecast(5))


def test_integer_array(reset_randomstate):
    rs = np.random.RandomState(12345)
    e = 10*rs.standard_normal((1000,2))
    y_star = np.cumsum(e[:,0])
    y = y_star + e[:,1]
    y = y.astype(np.long)
    res = ExponentialSmoothing(y,trend='add').fit()
    assert res.params['smoothing_level'] != 0.0


def test_damping_slope_zero():
    endog = np.arange(10)
    mod = ExponentialSmoothing(endog, trend='add', damped=True)
    res1 = mod.fit(smoothing_level=1, smoothing_slope=0.0, damping_slope=1e-20)
    pred1 = res1.predict(start=0)
    assert_allclose(pred1, np.r_[0., np.arange(9)], atol=1e-10)

    res2 = mod.fit(smoothing_level=1, smoothing_slope=0.0, damping_slope=0)
    pred2 = res2.predict(start=0)
    assert_allclose(pred2, np.r_[0., np.arange(9)], atol=1e-10)

    assert_allclose(pred1, pred2, atol=1e-10)



@pytest.fixture
def austourists():
    # austourists dataset from fpp2 package
    # https://cran.r-project.org/web/packages/fpp2/index.html
    data = [30.05251, 19.14850, 25.31769, 27.59144, 32.07646,
            23.48796, 28.47594, 35.12375, 36.83848, 25.00702,
            30.72223, 28.69376, 36.64099, 23.82461, 29.31168,
            31.77031, 35.17788, 19.77524, 29.60175, 34.53884,
            41.27360, 26.65586, 28.27986, 35.19115, 42.20566,
            24.64917, 32.66734, 37.25735, 45.24246, 29.35048,
            36.34421, 41.78208, 49.27660, 31.27540, 37.85063,
            38.83704, 51.23690, 31.83855, 41.32342, 42.79900,
            55.70836, 33.40714, 42.31664, 45.15712, 59.57608,
            34.83733, 44.84168, 46.97125, 60.01903, 38.37118,
            46.97586, 50.73380, 61.64687, 39.29957, 52.67121,
            54.33232, 66.83436, 40.87119, 51.82854, 57.49191,
            65.25147, 43.06121, 54.76076, 59.83447, 73.25703,
            47.69662, 61.09777, 66.05576,]
    index = pd.date_range("1999-03-01", "2015-12-01", freq="3MS")
    return pd.Series(data, index)


@pytest.fixture
def simulate_expected_results_R():
    """
    obtained from ets.simulate in the R package forecast, data is from fpp2
    package.

    library(magrittr)
    library(fpp2)
    library(forecast)
    concat <- function(...) {
      return(paste(..., sep=""))
    }
    error <- c("A", "M")
    trend <- c("A", "M", "N")
    seasonal <- c("A", "M", "N")
    models <- outer(error, trend, FUN = "concat") %>%
      outer(seasonal, FUN = "concat") %>% as.vector
    # innov from np.random.seed(0); np.random.randn(4)
    innov <- c(1.76405235, 0.40015721, 0.97873798, 2.2408932)
    params <- expand.grid(models, c(TRUE, FALSE))
    results <- apply(params, 1, FUN = function(p) {
      tryCatch(
        simulate(ets(austourists, model = p[1], damped = as.logical(p[2])),
                 innov = innov),
        error = function(e) c(NA, NA, NA, NA))
    }) %>% t
    rownames(results) <- apply(params, 1, FUN = function(x) paste(x[1], x[2]))
    """
    damped = {
        "AAA": [ 77.84173,  52.69818,  65.83254,  71.85204],
        "MAA": [207.81653, 136.97700, 253.56234, 588.95800],
        "MAM": [215.83822, 127.17132, 269.09483, 704.32105],
        "MMM": [216.52591, 132.47637, 283.04889, 759.08043],
        "AAN": [ 62.51423,  61.87381,  63.14735,  65.11360],
        "MAN": [168.25189,  90.46201, 133.54769, 232.81738],
        "MMN": [167.97747,  90.59675, 134.20300, 235.64502],
    }
    undamped = {
        "AAA": [ 77.10860,  51.51669,  64.46857,   70.36349],
        "MAA": [209.23158, 149.62943, 270.65579,  637.03828],
        "ANA": [ 77.09320,  51.52384,  64.36231,   69.84786],
        "MNA": [207.86986, 169.42706, 313.97960,  793.97948],
        "MAM": [214.45750, 106.19605, 211.61304,  492.12223],
        "MMM": [221.01861, 158.55914, 403.22625, 1389.33384],
        "MNM": [215.00997, 140.93035, 309.92465,  875.07985],
        "AAN": [ 63.66619,  63.09571,  64.45832,   66.51967],
        "MAN": [172.37584,  91.51932, 134.11221,  230.98970],
        "MMN": [169.88595,  97.33527, 142.97017,  252.51834],
        "ANN": [ 60.53589,  59.51851,  60.17570,   61.63011],
        "MNN": [163.01575, 112.58317, 172.21992,  338.93918],
    }
    return {True: damped, False: undamped}

@pytest.fixture
def simulate_fit_state_R():
    """
    The final state from the R model fits to get an exact comparison
    Obtained with this R script:

    library(magrittr)
    library(fpp2)
    library(forecast)

    concat <- function(...) {
      return(paste(..., sep=""))
    }

    as_dict_string <- function(named) {
      string <- '{'
      for (name in names(named)) {
        string <- concat(string, "\"", name, "\": ", named[name], ", ")
      }
      string <- concat(string, '}')
      return(string)
    }

    get_var <- function(named, name) {
      if (name %in% names(named))
        val <- c(named[name])
      else
        val <- c(NaN)
      names(val) <- c(name)
      return(val)
    }

    error <- c("A", "M")
    trend <- c("A", "M", "N")
    seasonal <- c("A", "M", "N")
    models <- outer(error, trend, FUN = "concat") %>%
      outer(seasonal, FUN = "concat") %>% as.vector

    # innov from np.random.seed(0); np.random.randn(4)
    innov <- c(1.76405235, 0.40015721, 0.97873798, 2.2408932)
    n <- length(austourists) + 1

    # print fit parameters and final states
    for (damped in c(TRUE, FALSE)) {
      print(paste("damped =", damped))
      for (model in models) {
        state <- tryCatch((function(){
          fit <- ets(austourists, model = model, damped = damped)
          pars <- c()
          # alpha, beta, gamma, phi
          for (name in c("alpha", "beta", "gamma", "phi")) {
            pars <- c(pars, get_var(fit$par, name))
          }
          # l, b, s1, s2, s3, s4
          states <- c()
          for (name in c("l", "b", "s1", "s2", "s3", "s4"))
            states <- c(states, get_var(fit$states[n,], name))
          c(pars, states)
        })(),
        error = function(e) rep(NA, 10))
        cat(concat("\"", model, "\": ", as_dict_string(state), ",\n"))
      }
    }
    """
    damped = {
        "AAA": {"alpha": 0.35445427317618, "beta": 0.0320074905894167,
                "gamma": 0.399933869627979, "phi": 0.979999965983533,
                "l": 62.003405788717, "b": 0.706524957599738,
                "s1": 3.58786406600866, "s2": -0.0747450283892903,
                "s3": -11.7569356589817, "s4": 13.3818805055271, },
        "MAA": {"alpha": 0.31114284033284, "beta": 0.0472138763848083,
                "gamma": 0.309502324693322, "phi": 0.870889202791893,
                "l": 59.2902342851514, "b": 0.62538315801909,
                "s1": 5.66660224738038, "s2": 2.16097311633352,
                "s3": -9.20020909069337, "s4": 15.3505801601698, },
        "MAM": {"alpha": 0.483975835390643, "beta": 0.00351728130401287,
                "gamma": 0.00011309784353818, "phi": 0.979999998322032,
                "l": 63.0042707536293, "b": 0.275035160634846,
                "s1": 1.03531670491486, "s2": 0.960515682506077,
                "s3": 0.770086097577864, "s4": 1.23412213281709, },
        "MMM": {"alpha": 0.523526123191035, "beta": 0.000100021136675999,
                "gamma": 0.000100013723372502, "phi": 0.971025672907157,
                "l": 63.2030316675533, "b": 1.00458391644788,
                "s1": 1.03476354353096, "s2": 0.959953222294316,
                "s3": 0.771346403552048, "s4": 1.23394845160922, },
        "AAN": {"alpha": 0.014932817259302, "beta": 0.0149327068053362,
                "gamma": np.nan, "phi": 0.979919958387887,
                "l": 60.0651024395378, "b": 0.699112782133822,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        "MAN": {"alpha": 0.0144217343786778, "beta": 0.0144216994589862,
                "gamma": np.nan, "phi": 0.979999719878659,
                "l": 60.1870032363649, "b": 0.698421913047609,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        "MMN": {"alpha": 0.015489181776072, "beta": 0.0154891632646377,
                "gamma": np.nan, "phi": 0.975139118496093,
                "l": 60.1855946424729, "b": 1.00999589024928,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        }
    undamped = {
        "AAA": {"alpha": 0.20281951627363, "beta": 0.000169786227368617,
                "gamma": 0.464523797585052, "phi": np.nan,
                "l": 62.5598121416791, "b": 0.578091734736357,
                "s1": 2.61176734723357, "s2": -1.24386240029203,
                "s3": -12.9575427049515, "s4": 12.2066400808086, },
        "MAA": {"alpha": 0.416371920801538, "beta": 0.000100008012920072,
                "gamma": 0.352943901103959, "phi": np.nan,
                "l": 62.0497742976079, "b": 0.450130087198346,
                "s1": 3.50368220490457, "s2": -0.0544297321113539,
                "s3": -11.6971093199679, "s4": 13.1974985095916, },
        "ANA": {"alpha": 0.54216694759434, "beta": np.nan,
                "gamma": 0.392030170511872, "phi": np.nan,
                "l": 57.606831186929, "b": np.nan,
                "s1": 8.29613785790501, "s2": 4.6033791939889,
                "s3": -7.43956343440823, "s4": 17.722316385643, },
        "MNA": {"alpha": 0.532842556756286, "beta": np.nan,
                "gamma": 0.346387433608713, "phi": np.nan,
                "l": 58.0372808528325, "b": np.nan,
                "s1": 7.70802088750111, "s2": 4.14885814748503,
                "s3": -7.72115936226225, "s4": 17.1674660340923, },
        "MAM": {"alpha": 0.315621390571192, "beta": 0.000100011993615961,
                "gamma": 0.000100051297784532, "phi": np.nan,
                "l": 62.4082004238551, "b": 0.513327867101983,
                "s1": 1.03713425342421, "s2": 0.959607104686072,
                "s3": 0.770172817592091, "s4": 1.23309264451638, },
        "MMM": {"alpha": 0.546068965886, "beta": 0.0737816453485457,
                "gamma": 0.000100031693302807, "phi": np.nan,
                "l": 63.8203866275649, "b": 1.01833305374778,
                "s1": 1.03725227137871, "s2": 0.961177239042923,
                "s3": 0.771173487523454, "s4": 1.23036313932852, },
        "MNM": {"alpha": 0.608993139624813, "beta": np.nan,
                "gamma": 0.000167258612971303, "phi": np.nan,
                "l": 63.1472153330648, "b": np.nan,
                "s1": 1.0384840572776, "s2": 0.961456755855531,
                "s3": 0.768427399477366, "s4": 1.23185085956321, },
        "AAN": {"alpha": 0.0097430554119077, "beta": 0.00974302759255084,
                "gamma": np.nan, "phi": np.nan,
                "l": 61.1430969243248, "b": 0.759041621012503,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        "MAN": {"alpha": 0.0101749952821338, "beta": 0.0101749138539332,
                "gamma": np.nan, "phi": np.nan,
                "l": 61.6020426238699, "b": 0.761407500773051,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        "MMN": {"alpha": 0.0664382968951546, "beta": 0.000100001678373356,
                "gamma": np.nan, "phi": np.nan,
                "l": 60.7206911970871, "b": 1.01221899136391,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        "ANN": {"alpha": 0.196432515825523, "beta": np.nan,
                "gamma": np.nan, "phi": np.nan,
                "l": 58.7718395431632, "b": np.nan,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
        "MNN": {"alpha": 0.205985314333856, "beta": np.nan,
                "gamma": np.nan, "phi": np.nan,
                "l": 58.9770839944419, "b": np.nan,
                "s1": np.nan, "s2": np.nan,
                "s3": np.nan, "s4": np.nan, },
    }
    return {True: damped, False: undamped}


@pytest.mark.parametrize('trend', TRENDS)
@pytest.mark.parametrize('seasonal', SEASONALS)
@pytest.mark.parametrize('damped', (True, False))
@pytest.mark.parametrize('error', ("add", "mul"))
def test_simulate_expected_R(trend, seasonal, damped, error,
                             austourists, simulate_expected_results_R,
                             simulate_fit_state_R):
    """
    Test for :meth:``statsmodels.tsa.holtwinters.HoltWintersResults``.

    The tests are using the implementation in the R package ``forecast`` as
    reference, and example data is taken from ``fpp2`` (package and book).
    """

    short_name = {"add": "A", "mul": "M", None: "N"}
    model_name = short_name[error] +  short_name[trend] + short_name[seasonal]
    if model_name in simulate_expected_results_R[damped]:
        expected = np.asarray(simulate_expected_results_R[damped][model_name])
        state = simulate_fit_state_R[damped][model_name]
    else:
        return

    # create HoltWintersResults object with same parameters as in R
    fit = ExponentialSmoothing(
        austourists, seasonal_periods=4,
        trend=trend, seasonal=seasonal, damped=damped
    ).fit(
        smoothing_level=state["alpha"], smoothing_slope=state["beta"],
        smoothing_seasonal=state["gamma"], damping_slope=state["phi"],
        optimized=False
    )

    # set the same final state as in R
    fit.level[-1] = state["l"]
    fit.slope[-1] = state["b"]
    fit.season[-1] = state["s1"]
    fit.season[-2] = state["s2"]
    fit.season[-3] = state["s3"]
    fit.season[-4] = state["s4"]

    # for MMM with damped trend the fit fails
    if np.any(np.isnan(fit.fittedvalues)):
        return

    innov = np.asarray([[1.76405235, 0.40015721, 0.97873798, 2.2408932]]).T
    sim = fit.simulate(4, repetitions=1, error=error, random_errors=innov)

    assert_almost_equal(expected, sim.values, 5)


def test_simulate_keywords(austourists):
    """
    check whether all keywords are accepted and work without throwing errors.
    """
    fit = ExponentialSmoothing(
        austourists, seasonal_periods=4,
        trend="add", seasonal="add", damped=True
    ).fit()

    # test anchor
    assert_almost_equal(
        fit.simulate(4, anchor=0, random_state=0).values,
        fit.simulate(4, anchor="start", random_state=0).values
    )
    assert_almost_equal(
        fit.simulate(4, anchor=-1, random_state=0).values,
        fit.simulate(4, anchor="2015-12-01", random_state=0).values
    )
    assert_almost_equal(
        fit.simulate(4, anchor="end", random_state=0).values,
        fit.simulate(4, anchor="2016-03-01", random_state=0).values
    )

    # test different random error options
    fit.simulate(4, repetitions=10, random_errors=scipy.stats.norm)
    fit.simulate(4, repetitions=10, random_errors=scipy.stats.norm())

    fit.simulate(4, repetitions=10, random_errors=np.random.randn(4,10))
    fit.simulate(4, repetitions=10, random_errors="bootstrap")

    # test seeding
    res = fit.simulate(4, repetitions=10, random_state=10).values
    res2 = fit.simulate(
        4, repetitions=10, random_state=np.random.RandomState(10)
    ).values
    assert np.all(res == res2)


def test_simulate_boxcox(austourists):
    """
    check if simulation results with boxcox fits are reasonable
    """
    fit = ExponentialSmoothing(
        austourists, seasonal_periods=4,
        trend="add", seasonal="mul", damped=False
    ).fit(use_boxcox=True)
    expected = fit.forecast(4).values

    res = fit.simulate(4, repetitions=10).values
    mean = np.mean(res, axis=1)

    assert np.all(np.abs(mean - expected) < 5)
