# Copyright 2018-2022 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import json as json
import types
from typing import cast, Any, List, Tuple, Type

import numpy as np

import streamlit
from streamlit import type_util
from streamlit.errors import StreamlitAPIException
from streamlit.state.session_state import LazySessionState

# Special methods:

HELP_TYPES = (
    types.BuiltinFunctionType,
    types.BuiltinMethodType,
    types.FunctionType,
    types.MethodType,
    types.ModuleType,
)  # type: Tuple[Type[Any], ...]


class WriteMixin:
    def write(self, *args, **kwargs):
        """Write arguments to the app.

        This is the Swiss Army knife of Streamlit commands: it does different
        things depending on what you throw at it. Unlike other Streamlit commands,
        write() has some unique properties:

        1. You can pass in multiple arguments, all of which will be written.
        2. Its behavior depends on the input types as follows.
        3. It returns None, so its "slot" in the App cannot be reused.

        Parameters
        ----------
        *args : any
            One or many objects to print to the App.

            Arguments are handled as follows:

            - write(string)     : Prints the formatted Markdown string, with
                support for LaTeX expression and emoji shortcodes.
                See docs for st.markdown for more.
            - write(data_frame) : Displays the DataFrame as a table.
            - write(error)      : Prints an exception specially.
            - write(func)       : Displays information about a function.
            - write(module)     : Displays information about the module.
            - write(dict)       : Displays dict in an interactive widget.
            - write(mpl_fig)    : Displays a Matplotlib figure.
            - write(altair)     : Displays an Altair chart.
            - write(keras)      : Displays a Keras model.
            - write(graphviz)   : Displays a Graphviz graph.
            - write(plotly_fig) : Displays a Plotly figure.
            - write(bokeh_fig)  : Displays a Bokeh figure.
            - write(sympy_expr) : Prints SymPy expression using LaTeX.
            - write(htmlable)   : Prints _repr_html_() for the object if available.
            - write(obj)        : Prints str(obj) if otherwise unknown.

        unsafe_allow_html : bool
            This is a keyword-only argument that defaults to False.

            By default, any HTML tags found in strings will be escaped and
            therefore treated as pure text. This behavior may be turned off by
            setting this argument to True.

            That said, *we strongly advise against it*. It is hard to write secure
            HTML, so by using this argument you may be compromising your users'
            security. For more information, see:

            https://github.com/streamlit/streamlit/issues/152

            **Also note that `unsafe_allow_html` is a temporary measure and may be
            removed from Streamlit at any time.**

            If you decide to turn on HTML anyway, we ask you to please tell us your
            exact use case here:
            https://discuss.streamlit.io/t/96 .

            This will help us come up with safe APIs that allow you to do what you
            want.

        Example
        -------

        Its basic use case is to draw Markdown-formatted text, whenever the
        input is a string:

        >>> write('Hello, *World!* :sunglasses:')

        ..  output::
            https://static.streamlit.io/0.50.2-ZWk9/index.html?id=Pn5sjhgNs4a8ZbiUoSTRxE
            height: 50px

        As mentioned earlier, `st.write()` also accepts other data formats, such as
        numbers, data frames, styled data frames, and assorted objects:

        >>> st.write(1234)
        >>> st.write(pd.DataFrame({
        ...     'first column': [1, 2, 3, 4],
        ...     'second column': [10, 20, 30, 40],
        ... }))

        ..  output::
            https://static.streamlit.io/0.25.0-2JkNY/index.html?id=FCp9AMJHwHRsWSiqMgUZGD
            height: 250px

        Finally, you can pass in multiple arguments to do things like:

        >>> st.write('1 + 1 = ', 2)
        >>> st.write('Below is a DataFrame:', data_frame, 'Above is a dataframe.')

        ..  output::
            https://static.streamlit.io/0.25.0-2JkNY/index.html?id=DHkcU72sxYcGarkFbf4kK1
            height: 300px

        Oh, one more thing: `st.write` accepts chart objects too! For example:

        >>> import pandas as pd
        >>> import numpy as np
        >>> import altair as alt
        >>>
        >>> df = pd.DataFrame(
        ...     np.random.randn(200, 3),
        ...     columns=['a', 'b', 'c'])
        ...
        >>> c = alt.Chart(df).mark_circle().encode(
        ...     x='a', y='b', size='c', color='c', tooltip=['a', 'b', 'c'])
        >>>
        >>> st.write(c)

        ..  output::
            https://static.streamlit.io/0.25.0-2JkNY/index.html?id=8jmmXR8iKoZGV4kXaKGYV5
            height: 200px

        """
        string_buffer = []  # type: List[str]
        unsafe_allow_html = kwargs.get("unsafe_allow_html", False)

        # This bans some valid cases like: e = st.empty(); e.write("a", "b").
        # BUT: 1) such cases are rare, 2) this rule is easy to understand,
        # and 3) this rule should be removed once we have st.container()
        if not self.dg._is_top_level and len(args) > 1:
            raise StreamlitAPIException(
                "Cannot replace a single element with multiple elements.\n\n"
                "The `write()` method only supports multiple elements when "
                "inserting elements rather than replacing. That is, only "
                "when called as `st.write()` or `st.sidebar.write()`."
            )

        def flush_buffer():
            if string_buffer:
                self.dg.markdown(
                    " ".join(string_buffer),
                    unsafe_allow_html=unsafe_allow_html,
                )
                string_buffer[:] = []

        for arg in args:
            # Order matters!
            if isinstance(arg, str):
                string_buffer.append(arg)
            elif type_util.is_dataframe_like(arg):
                flush_buffer()
                if len(np.shape(arg)) > 2:
                    self.dg.text(arg)
                else:
                    self.dg.dataframe(arg)
            elif isinstance(arg, Exception):
                flush_buffer()
                self.dg.exception(arg)
            elif isinstance(arg, HELP_TYPES):
                flush_buffer()
                self.dg.help(arg)
            elif type_util.is_altair_chart(arg):
                flush_buffer()
                self.dg.altair_chart(arg)
            elif type_util.is_type(arg, "matplotlib.figure.Figure"):
                flush_buffer()
                self.dg.pyplot(arg)
            elif type_util.is_plotly_chart(arg):
                flush_buffer()
                self.dg.plotly_chart(arg)
            elif type_util.is_type(arg, "bokeh.plotting.figure.Figure"):
                flush_buffer()
                self.dg.bokeh_chart(arg)
            elif type_util.is_graphviz_chart(arg):
                flush_buffer()
                self.dg.graphviz_chart(arg)
            elif type_util.is_sympy_expession(arg):
                flush_buffer()
                self.dg.latex(arg)
            elif type_util.is_keras_model(arg):
                from tensorflow.python.keras.utils import vis_utils

                flush_buffer()
                dot = vis_utils.model_to_dot(arg)
                self.dg.graphviz_chart(dot.to_string())
            elif isinstance(arg, (dict, list, LazySessionState)):
                flush_buffer()
                self.dg.json(arg)
            elif type_util.is_namedtuple(arg):
                flush_buffer()
                self.dg.json(json.dumps(arg._asdict()))
            elif type_util.is_pydeck(arg):
                flush_buffer()
                self.dg.pydeck_chart(arg)
            elif inspect.isclass(arg):
                flush_buffer()
                self.dg.text(arg)
            elif hasattr(arg, "_repr_html_"):
                self.dg.markdown(
                    arg._repr_html_(),
                    unsafe_allow_html=True,
                )
            else:
                string_buffer.append("`%s`" % str(arg).replace("`", "\\`"))

        flush_buffer()

    @property
    def dg(self) -> "streamlit.delta_generator.DeltaGenerator":
        """Get our DeltaGenerator."""
        return cast("streamlit.delta_generator.DeltaGenerator", self)
