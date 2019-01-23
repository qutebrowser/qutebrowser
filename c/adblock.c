// This file is part of webmacs.
//
// webmacs is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// webmacs is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with webmacs.  If not, see <http://www.gnu.org/licenses/>.

#include <Python.h>
#include "structmember.h"

#include <iostream>
#include <fstream>

#include "ad_block_client.h"

using namespace std;

typedef struct {
  PyObject_HEAD

  AdBlockClient * client;
  char * data;
} AdBlock;


static void
AdBlock_dealloc(AdBlock* self)
{
  delete self->client;
  if (self->data) delete[] self->data;
  Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
AdBlock_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
  AdBlock *self;

  self = (AdBlock *)type->tp_alloc(type, 0);

  return (PyObject *)self;
}

static int
AdBlock_init(AdBlock *self, PyObject *args, PyObject *kwds)
{
  self->client = new AdBlockClient;
  self->data = NULL;
  return 0;
}

static PyObject *
AdBlock_parse(AdBlock* self, PyObject *args)
{
  const char *data;

  if (!PyArg_ParseTuple(args, "s", &data))
    return NULL;

  Py_BEGIN_ALLOW_THREADS
  self->client->parse(data);
  Py_END_ALLOW_THREADS

  Py_RETURN_NONE;
}

static PyObject *
AdBlock_matches(AdBlock* self, PyObject *args)
{
  const char *url, *domain;
  bool result;

  if (!PyArg_ParseTuple(args, "ss", &url, &domain))
    return NULL;

  /* I suspect that allowing threads here does create deadlocks,
   but anyway I am not sure it would be useful to allow them. */
  /* Py_BEGIN_ALLOW_THREADS */
  result = self->client->matches(url, FONoFilterOption, domain);
  /* Py_END_ALLOW_THREADS */

  if (result) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}

static PyObject *
AdBlock_save(AdBlock* self, PyObject *args)
{
  const char *path;

  if (!PyArg_ParseTuple(args, "s", &path))
    return NULL;

  int size;
  ofstream outFile(path, ios::out | ios::binary);
  if (!outFile) {
    Py_RETURN_FALSE;
  }

  Py_BEGIN_ALLOW_THREADS
  char * buffer = self->client->serialize(&size);
  outFile.write(buffer, size);
  outFile.close();
  Py_END_ALLOW_THREADS

  Py_RETURN_TRUE;
}

static PyObject *
AdBlock_load(AdBlock* self, PyObject *args)
{
  const char *path;
  bool result = false;

  if (!PyArg_ParseTuple(args, "s", &path))
    return NULL;

  ifstream file(path, ios::binary | ios::ate);
  if (!file) {
    Py_RETURN_FALSE;
  }

  Py_BEGIN_ALLOW_THREADS
  streamsize size = file.tellg();
  file.seekg(0, ios::beg);

  if (self->data) {delete[] self->data;}
  self->data = new char[size];
  if (file.read(self->data, size)) {
    self->client->deserialize(self->data);
    result = true;
  }
  Py_END_ALLOW_THREADS

  if (result) {
    Py_RETURN_TRUE;
  } else {
    Py_RETURN_FALSE;
  }
}


static PyMethodDef AdBlock_methods[] = {
  {"parse", (PyCFunction)AdBlock_parse, METH_VARARGS,
   "Parse adblock data string, like the content of an easylist."
  },
  {"matches", (PyCFunction)AdBlock_matches, METH_VARARGS,
   "matches an url, returns True if it should be filtered."
  },
  {"save", (PyCFunction)AdBlock_save, METH_VARARGS,
   "Save serialized data into a file."
  },
  {"load", (PyCFunction)AdBlock_load, METH_VARARGS,
   "Load serialized data from a file."
  },
  {NULL}  /* Sentinel */
};

static PyTypeObject AdBlockType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "adblock.AdBlock",             /* tp_name */
    sizeof(AdBlock),             /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)AdBlock_dealloc, /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    0,                         /* tp_hash  */
    0,                         /* tp_call */
    0,                         /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT |
        Py_TPFLAGS_BASETYPE,   /* tp_flags */
    "Adblock objects",           /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    AdBlock_methods,             /* tp_methods */
    0,             /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)AdBlock_init,      /* tp_init */
    0,                         /* tp_alloc */
    AdBlock_new,                 /* tp_new */
};


static PyModuleDef adblockmodule = {
  PyModuleDef_HEAD_INIT,
  "adblock",
  "Module to speed up ad filtering.",
  -1,
  NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC
PyInit__adblock(void)
{
  PyObject* m;

  AdBlockType.tp_new = PyType_GenericNew;
  if (PyType_Ready(&AdBlockType) < 0)
    return NULL;

  m = PyModule_Create(&adblockmodule);
  if (m == NULL)
    return NULL;

  Py_INCREF(&AdBlockType);
  PyModule_AddObject(m, "AdBlock", (PyObject *)&AdBlockType);
  return m;
}
